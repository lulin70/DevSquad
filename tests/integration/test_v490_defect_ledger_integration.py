"""
V4.9.0 W1 Defect Ledger Integration Tests

集成测试：defect_ledger.py 与 dispatch_audit.py 的真实集成场景。
覆盖：signal_ref 解析、状态机转换、跨模块数据流、CLI 命令集成。
"""

import json
import sqlite3

import pytest

from scripts.collaboration.defect_ledger import (
    DefectLedger,
    DefectLedgerError,
    DefectState,
    mandatory_signal_types,
)
from scripts.collaboration.dispatch_audit import DispatchAuditLogger
from scripts.collaboration.two_stage_review_gate import ReviewFinding, ReviewStage

pytestmark = pytest.mark.integration


def _finding(category: str, severity: str = "warning", stage: ReviewStage = ReviewStage.CODE_QUALITY) -> dict:
    """真实 ReviewFinding 的落库形状（BV 类别码放在 category）。"""
    return ReviewFinding(
        stage=stage,
        severity=severity,
        category=category,
        description=f"review hit {category}",
        file_path="api/routes.py",
        line_range="42",
        suggestion=f"Review and fix {category}.",
    ).to_dict()


def _log_end(
    logger: DispatchAuditLogger,
    user_id: str,
    *,
    findings: list[dict] | None = None,
    failure_class: str | None = None,
    success: bool = False,
    duration: float = 1.0,
) -> None:
    """写一个真实的 dispatch_end 审计事件（可选 findings / failure_class）。"""
    logger.log_dispatch_end(
        user_id=user_id,
        success=success,
        duration=duration,
        findings=findings,
        failure_class=failure_class,
    )


class TestDefectLedgerAuditIntegration:
    """缺陷台账与审计日志集成"""

    def test_signal_ref_parsing_from_real_audit_db(self, tmp_path):
        """测试从真实 audit DB 解析 signal_ref"""
        # 创建真实审计日志（构造函数只接受 Path）
        audit_path = tmp_path / "test_audit.db"
        logger = DispatchAuditLogger(audit_path)

        # 写入一个 dispatch 事件（带 findings）
        logger.log_dispatch_start("test-task-001", "mock", ["architect"])
        _log_end(
            logger,
            "test-task-001",
            findings=[_finding("VULN-1", "critical")],
            failure_class="product_failed",
        )
        logger.close()

        # 创建台账并解析 signal_ref（事件 1 是 start，事件 2 是 end）
        ledger_path = tmp_path / "defects.json"
        ledger = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)

        defect = ledger.add("audit:event=2&finding=0", "SQL injection found in auth.py")

        # 验证 signal_ref 可解析且缺陷为 open
        assert defect.id == "DEF-001"
        assert defect.state is DefectState.OPEN
        assert defect.signal["ref"] == "audit:event=2&finding=0"
        # BV 类别码按 PRD §4.2 映射为 review:break-vuln:<ID>
        assert defect.signal["type"] == "review:break-vuln:VULN-1"

        # 验证可以从 audit DB 提取实际 finding 内容（JSON 存在 details 列）
        conn = sqlite3.connect(str(audit_path))
        row = conn.execute("SELECT details FROM dispatch_audit WHERE id = 2").fetchone()
        assert row is not None
        findings_data = json.loads(row[0])["findings"]
        assert findings_data[0]["category"] == "VULN-1"
        conn.close()

    def test_full_lifecycle_with_audit_correlation(self, tmp_path):
        """测试完整生命周期：open → fixed → closed，关联 audit 事件"""
        audit_path = tmp_path / "lifecycle_audit.db"
        ledger_path = tmp_path / "lifecycle_defects.json"

        # Step 1: 审计发现问题（事件 1 = 发现，事件 2 = 干净回归跑）
        logger = DispatchAuditLogger(audit_path)
        _log_end(
            logger,
            "task-lifecycle",
            findings=[_finding("missing_error_handling", stage=ReviewStage.SPEC_COMPLIANCE)],
            failure_class="product_failed",
        )
        _log_end(logger, "task-verify", success=True, failure_class="none")
        logger.close()

        # Step 2: 登记缺陷（signal_ref 必须解析成功）
        ledger = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        defect = ledger.add("audit:event=1&finding=0", "Missing error handling in module X")
        assert defect.state is DefectState.OPEN

        # Step 3: 标记为已修复（要求 commit SHA + summary）
        defect = ledger.update("DEF-001", "abc1234", "Added try-catch blocks")
        assert defect.state is DefectState.FIXED
        assert defect.fix["commit"] == "abc1234"

        # Step 4: 验证修复（clean run），关闭缺陷
        defect = ledger.close("DEF-001", "audit:event=2")
        assert defect.state is DefectState.CLOSED
        assert defect.regression["run_ref"] == "audit:event=2"

        # Step 5: 验证 signal_ref 始终保留
        assert defect.signal["ref"] == "audit:event=1&finding=0"

    def test_multiple_defects_same_audit_event(self, tmp_path):
        """测试多个缺陷引用同一审计事件的不同 findings"""
        audit_path = tmp_path / "multi_audit.db"
        ledger_path = tmp_path / "multi_defects.json"

        # 审计发现多个问题
        logger = DispatchAuditLogger(audit_path)
        _log_end(
            logger,
            "task-multi",
            findings=[
                _finding("VULN-1", "critical"),
                _finding("BREAK-1", "critical"),
                _finding("missing_input_validation", stage=ReviewStage.SPEC_COMPLIANCE),
            ],
            failure_class="product_failed",
        )
        logger.close()

        # 为每个 finding 登记独立缺陷（finding 下标 0-based）
        ledger = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)

        defect1 = ledger.add("audit:event=1&finding=0", "Fix ORM object leak")
        defect2 = ledger.add("audit:event=1&finding=1", "Add missing route handler")
        defect3 = ledger.add("audit:event=1&finding=2", "Add input validation")

        # 验证三个缺陷独立存在
        assert defect1.id != defect2.id != defect3.id
        assert [defect1.id, defect2.id, defect3.id] == ["DEF-001", "DEF-002", "DEF-003"]
        assert defect1.signal["type"] == "review:break-vuln:VULN-1"
        assert defect2.signal["type"] == "review:break-vuln:BREAK-1"
        assert defect3.signal["type"] == "review:spec:missing_input_validation"

        # 验证都引用同一事件
        all_defects = ledger.list_defects()
        assert all(d.signal["ref"].startswith("audit:event=1") for d in all_defects)


class TestDefectLedgerCLIIntegration:
    """缺陷台账 CLI 命令集成测试"""

    def test_cli_add_list_workflow(self, tmp_path):
        """测试 CLI add → list 工作流"""
        audit_path = tmp_path / "cli_audit.db"
        ledger_path = tmp_path / "cli_defects.json"

        logger = DispatchAuditLogger(audit_path)
        _log_end(logger, "cli-add", findings=[_finding("BREAK-2")])
        logger.close()

        # 模拟 CLI add 命令：add 只接受 signal_ref + summary
        ledger = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        defect = ledger.add("audit:event=1&finding=0", "CLI test defect")

        # 模拟 CLI list 命令
        all_defects = ledger.list_defects()
        assert len(all_defects) == 1
        assert all_defects[0].id == defect.id
        assert all_defects[0].signal["summary"] == "CLI test defect"
        assert all_defects[0].state is DefectState.OPEN

    def test_cli_update_close_reopen_workflow(self, tmp_path):
        """测试 CLI update → close → reopen 工作流"""
        audit_path = tmp_path / "cli_lifecycle_audit.db"
        ledger_path = tmp_path / "cli_lifecycle.json"

        logger = DispatchAuditLogger(audit_path)
        _log_end(
            logger,
            "cli-lifecycle",
            findings=[_finding("flaky_test", stage=ReviewStage.SPEC_COMPLIANCE)],
            failure_class="product_failed",
        )
        _log_end(logger, "cli-verify", success=True, failure_class="none")
        logger.close()

        ledger = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        defect = ledger.add("audit:event=1&finding=0", "Test intermittent failure")

        # 更新状态到 fixed
        defect = ledger.update(defect.id, "def5678", "Added retry logic")
        assert defect.state is DefectState.FIXED

        # 关闭缺陷（需要一次干净的回归跑引用）
        defect = ledger.close(defect.id, "audit:event=2")
        assert defect.state is DefectState.CLOSED

        # 重新打开（发现回归）
        defect = ledger.reopen(defect.id, "Regression detected in v4.9.1")
        assert defect.state is DefectState.OPEN
        # 验证 reopen 原因保留，历史记录 tail 为 reopen
        assert defect.reopen_reason == "Regression detected in v4.9.1"
        assert defect.history[-1]["transition"] == "reopen"


class TestDefectLedgerFailureMappingIntegration:
    """缺陷台账与 failure_class 映射集成测试"""

    def test_product_failed_mandatory_signal(self, tmp_path):
        """测试 product_failed 必须有信号引用（PRD §4.2 映射表）"""
        audit_path = tmp_path / "mapping_audit.db"
        ledger_path = tmp_path / "mapping_defects.json"

        logger = DispatchAuditLogger(audit_path)
        _log_end(logger, "mapping-run", failure_class="product_failed")
        logger.close()

        # product_failed 必须登记缺陷（signal_ref 指向真实事件）
        ledger = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        defect = ledger.add("audit:event=1&failure=product_failed", "Product failure requires filing")

        assert defect.signal["type"] == "failure:product_failed"
        assert "failure:product_failed" in mandatory_signal_types()
        assert defect.state is DefectState.OPEN

    def test_environment_blocked_cannot_file(self, tmp_path):
        """测试 environment_blocked 拒绝立案（PRD §4.2）"""
        audit_path = tmp_path / "blocked_audit.db"
        ledger_path = tmp_path / "blocked_defects.json"

        logger = DispatchAuditLogger(audit_path)
        _log_end(logger, "blocked-run", failure_class="environment_blocked")
        logger.close()

        ledger = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)

        # environment_blocked 不是产品缺陷：台账层面直接拒绝立案
        with pytest.raises(DefectLedgerError, match="environment_blocked"):
            ledger.add("audit:event=1&failure=environment_blocked", "Environment issue (should not file)")

        # 拒绝后台账仍为空，且没有留下条目
        assert ledger.list_defects() == []


class TestDefectLedgerPersistenceIntegration:
    """缺陷台账持久化集成测试"""

    def test_cross_process_persistence(self, tmp_path):
        """测试跨进程持久化（模拟多个 CLI 调用）"""
        audit_path = tmp_path / "persist_audit.db"
        ledger_path = tmp_path / "persistent_defects.json"

        logger = DispatchAuditLogger(audit_path)
        _log_end(
            logger,
            "persist-run",
            findings=[_finding("persist_case", stage=ReviewStage.SPEC_COMPLIANCE)],
        )
        logger.close()

        # 进程1：添加缺陷（add 内部完成原子写，无需 save）
        ledger1 = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        defect = ledger1.add("audit:event=1&finding=0", "Test cross-process")
        del ledger1  # 模拟进程结束

        # 进程2：读取并更新
        ledger2 = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        stored = ledger2.list_defects()[0]
        assert stored.id == defect.id
        assert stored.signal["summary"] == "Test cross-process"

        ledger2.update(defect.id, "aaa1111", "Fixed in a later process")
        del ledger2

        # 进程3：验证更新已持久化
        ledger3 = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        stored = ledger3.list_defects()[0]
        assert stored.state is DefectState.FIXED
        assert stored.fix["commit"] == "aaa1111"

    def test_atomic_write_integrity(self, tmp_path):
        """测试原子写入完整性（tempfile + fsync + replace）"""
        audit_path = tmp_path / "atomic_audit.db"
        ledger_path = tmp_path / "atomic_defects.json"

        logger = DispatchAuditLogger(audit_path)
        _log_end(
            logger,
            "atomic-run",
            findings=[_finding(f"atomic_case_{i}", stage=ReviewStage.SPEC_COMPLIANCE) for i in range(5)],
        )
        logger.close()

        ledger = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)

        # 添加多个缺陷（每次 add 都是一次原子写）
        ids = []
        for i in range(5):
            defect = ledger.add(f"audit:event=1&finding={i}", f"Test atomic write {i}")
            ids.append(defect.id)

        # 验证文件存在且结构完整
        assert ledger_path.exists()
        payload = json.loads(ledger_path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == 1
        assert payload["next_id"] == 6
        assert [entry["id"] for entry in payload["entries"]] == ids

        # 验证没有残留的临时文件（原子写清理干净）
        assert list(tmp_path.glob(".defects-*.tmp")) == []

        # 重新加载验证完整性
        ledger_reloaded = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        assert [d.id for d in ledger_reloaded.list_defects()] == ids
        assert all(d.state is DefectState.OPEN for d in ledger_reloaded.list_defects())
        assert ledger_reloaded.audit_report() == []
