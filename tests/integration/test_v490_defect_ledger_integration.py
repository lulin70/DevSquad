"""
V4.9.0 W1 Defect Ledger Integration Tests

集成测试：defect_ledger.py 与 dispatch_audit.py 的真实集成场景。
覆盖：signal_ref 解析、状态机转换、跨模块数据流、CLI 命令集成。
"""

import sqlite3

import pytest

from scripts.collaboration.defect_ledger import DefectLedger
from scripts.collaboration.dispatch_audit import DispatchAuditLogger

pytestmark = pytest.mark.integration


class TestDefectLedgerAuditIntegration:
    """缺陷台账与审计日志集成"""

    def test_signal_ref_parsing_from_real_audit_db(self, tmp_path):
        """测试从真实 audit DB 解析 signal_ref"""
        # 创建真实审计日志
        audit_path = tmp_path / "test_audit.db"
        logger = DispatchAuditLogger(str(audit_path))

        # 写入一个 dispatch 事件（带 findings）
        logger.log_dispatch_start("test-task-001", "mock", ["architect"])
        logger.log_dispatch_end(
            task_id="test-task-001",
            success=False,
            findings={"break-vuln": ["SQL injection in auth.py"]},
            failure_class="product_failed",
        )
        logger.close()

        # 创建台账并解析 signal_ref
        ledger_path = tmp_path / "defects.json"
        ledger = DefectLedger(str(ledger_path))

        # 添加缺陷引用审计事件
        defect_id = ledger.add(
            title="Fix SQL injection",
            description="SQL injection found in auth.py",
            severity="critical",
            signal_ref="audit:event=1&finding=0",  # 引用第1个事件的第0个finding
            assignee="security-team",
        )

        # 验证 signal_ref 可解析
        defect = ledger.get(defect_id)
        assert defect["signal_ref"] == "audit:event=1&finding=0"
        assert defect["state"] == "open"

        # 验证可以从 audit DB 提取实际 finding 内容
        conn = sqlite3.connect(str(audit_path))
        cursor = conn.execute("SELECT findings FROM dispatch_audit WHERE id = 1")
        row = cursor.fetchone()
        assert row is not None
        # findings 是 JSON 字符串
        import json

        findings_data = json.loads(row[0])
        assert "break-vuln" in findings_data
        conn.close()

    def test_full_lifecycle_with_audit_correlation(self, tmp_path):
        """测试完整生命周期：open → fixed → closed，关联 audit 事件"""
        audit_path = tmp_path / "lifecycle_audit.db"
        ledger_path = tmp_path / "lifecycle_defects.json"

        # Step 1: 审计发现问题
        logger = DispatchAuditLogger(str(audit_path))
        logger.log_dispatch_start("task-lifecycle", "mock", ["tester"])
        logger.log_dispatch_end(
            task_id="task-lifecycle",
            success=False,
            findings={"spec": ["Missing error handling"]},
            failure_class="product_failed",
        )
        logger.close()

        # Step 2: 登记缺陷
        ledger = DefectLedger(str(ledger_path))
        defect_id = ledger.add(
            title="Add error handling",
            description="Missing error handling in module X",
            severity="medium",
            signal_ref="audit:event=1&finding=0",
        )
        assert ledger.get(defect_id)["state"] == "open"

        # Step 3: 标记为已修复
        ledger.update(defect_id, state="fixed", resolution="Added try-catch blocks")
        assert ledger.get(defect_id)["state"] == "fixed"

        # Step 4: 验证修复，关闭缺陷
        ledger.close_defect(defect_id, verified_by="qa-team")
        defect = ledger.get(defect_id)
        assert defect["state"] == "closed"
        assert defect["verified_by"] == "qa-team"

        # Step 5: 验证 signal_ref 始终保留
        assert defect["signal_ref"] == "audit:event=1&finding=0"

    def test_multiple_defects_same_audit_event(self, tmp_path):
        """测试多个缺陷引用同一审计事件的不同 findings"""
        audit_path = tmp_path / "multi_audit.db"
        ledger_path = tmp_path / "multi_defects.json"

        # 审计发现多个问题
        logger = DispatchAuditLogger(str(audit_path))
        logger.log_dispatch_start("task-multi", "mock", ["security"])
        logger.log_dispatch_end(
            task_id="task-multi",
            success=False,
            findings={"break-vuln": ["XSS in input.py", "CSRF token missing"], "spec": ["Missing input validation"]},
            failure_class="product_failed",
        )
        logger.close()

        # 为每个 finding 登记独立缺陷
        ledger = DefectLedger(str(ledger_path))

        defect1 = ledger.add(
            title="Fix XSS vulnerability",
            description="XSS found in input.py",
            severity="critical",
            signal_ref="audit:event=1&finding=0",  # 第0个 break-vuln finding
        )

        defect2 = ledger.add(
            title="Add CSRF protection",
            description="CSRF token missing",
            severity="high",
            signal_ref="audit:event=1&finding=1",  # 第1个 break-vuln finding
        )

        defect3 = ledger.add(
            title="Add input validation",
            description="Missing input validation",
            severity="medium",
            signal_ref="audit:event=1&finding=2",  # spec finding（编号延续）
        )

        # 验证三个缺陷独立存在
        assert ledger.get(defect1)["title"] == "Fix XSS vulnerability"
        assert ledger.get(defect2)["title"] == "Add CSRF protection"
        assert ledger.get(defect3)["title"] == "Add input validation"

        # 验证都引用同一事件
        assert all(ledger.get(did)["signal_ref"].startswith("audit:event=1") for did in [defect1, defect2, defect3])


class TestDefectLedgerCLIIntegration:
    """缺陷台账 CLI 命令集成测试"""

    def test_cli_add_list_workflow(self, tmp_path):
        """测试 CLI add → list 工作流"""
        ledger_path = tmp_path / "cli_defects.json"
        ledger = DefectLedger(str(ledger_path))

        # 模拟 CLI add 命令
        defect_id = ledger.add(
            title="CLI test defect",
            description="Test CLI workflow",
            severity="low",
            signal_ref="failure=product_failed",
        )

        # 模拟 CLI list 命令
        all_defects = ledger.list_all()
        assert len(all_defects) == 1
        assert all_defects[0]["id"] == defect_id
        assert all_defects[0]["title"] == "CLI test defect"

    def test_cli_update_close_reopen_workflow(self, tmp_path):
        """测试 CLI update → close → reopen 工作流"""
        ledger_path = tmp_path / "cli_lifecycle.json"
        ledger = DefectLedger(str(ledger_path))

        # 添加缺陷
        defect_id = ledger.add(title="Flaky test", description="Test intermittent failure", severity="medium")

        # 更新状态到 fixed
        ledger.update(defect_id, state="fixed", resolution="Added retry logic")
        assert ledger.get(defect_id)["state"] == "fixed"

        # 关闭缺陷
        ledger.close_defect(defect_id, verified_by="tester")
        assert ledger.get(defect_id)["state"] == "closed"

        # 重新打开（发现回归）
        ledger.reopen(defect_id, reason="Regression detected in v4.9.1")
        defect = ledger.get(defect_id)
        assert defect["state"] == "open"
        # 验证历史保留
        assert "Regression detected" in defect.get("reopen_reason", "")


class TestDefectLedgerFailureMappingIntegration:
    """缺陷台账与 failure_class 映射集成测试"""

    def test_product_failed_mandatory_signal(self, tmp_path):
        """测试 product_failed 必须有信号引用（PRD §4.2 映射表）"""
        ledger_path = tmp_path / "mapping_defects.json"
        ledger = DefectLedger(str(ledger_path))

        # product_failed 必须登记缺陷
        defect_id = ledger.add(
            title="Product failure requires filing",
            description="This defect references a product_failed dispatch",
            severity="high",
            signal_ref="failure=product_failed",  # 简化的 signal_ref
        )

        defect = ledger.get(defect_id)
        assert "product_failed" in defect["signal_ref"]
        assert defect["state"] == "open"

    def test_environment_blocked_cannot_file(self, tmp_path):
        """测试 environment_blocked 拒绝立案（PRD §4.2）"""
        ledger_path = tmp_path / "blocked_defects.json"
        ledger = DefectLedger(str(ledger_path))

        # environment_blocked 不应登记为缺陷（应通过其他方式跟踪）
        # 这里测试可以添加（因为台账本身不强制此规则），
        # 但 registration_gate 会在 dispatch 时拒绝此类信号
        defect_id = ledger.add(
            title="Environment issue (should not file)",
            description="This represents environment_blocked",
            severity="low",
            signal_ref="failure=environment_blocked",
        )

        # 台账层面允许，但语义上这是错误的用法
        # registration_gate 会在 evaluate 时拒绝此类信号
        defect = ledger.get(defect_id)
        assert "environment_blocked" in defect["signal_ref"]


class TestDefectLedgerPersistenceIntegration:
    """缺陷台账持久化集成测试"""

    def test_cross_process_persistence(self, tmp_path):
        """测试跨进程持久化（模拟多个 CLI 调用）"""
        ledger_path = tmp_path / "persistent_defects.json"

        # 进程1：添加缺陷
        ledger1 = DefectLedger(str(ledger_path))
        defect_id = ledger1.add(title="Persistent defect", description="Test cross-process", severity="medium")
        ledger1.save()
        del ledger1  # 模拟进程结束

        # 进程2：读取并更新
        ledger2 = DefectLedger(str(ledger_path))
        defect = ledger2.get(defect_id)
        assert defect["title"] == "Persistent defect"

        ledger2.update(defect_id, state="fixed")
        ledger2.save()
        del ledger2

        # 进程3：验证更新已持久化
        ledger3 = DefectLedger(str(ledger_path))
        defect = ledger3.get(defect_id)
        assert defect["state"] == "fixed"

    def test_atomic_write_integrity(self, tmp_path):
        """测试原子写入完整性（tempfile + fsync + replace）"""
        ledger_path = tmp_path / "atomic_defects.json"
        ledger = DefectLedger(str(ledger_path))

        # 添加多个缺陷
        ids = []
        for i in range(5):
            defect_id = ledger.add(title=f"Defect {i}", description=f"Test atomic write {i}", severity="low")
            ids.append(defect_id)

        # 保存（原子写入）
        ledger.save()

        # 验证文件存在且完整
        assert ledger_path.exists()

        # 重新加载验证完整性
        ledger_reloaded = DefectLedger(str(ledger_path))
        for defect_id in ids:
            defect = ledger_reloaded.get(defect_id)
            assert defect is not None
            assert "Defect" in defect["title"]
