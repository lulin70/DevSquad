"""
V4.9.0 End-to-End Dispatch → Gate Integration Tests

端到端测试：MultiAgentDispatcher.dispatch() → findings写入 → gate判定完整链路。
验证系统级健康性：信号不蒸发（PRD §1.1 F3）、gate在dispatch管道中的正确位置。
"""

import json
import sqlite3
import subprocess
import sys
import time
from typing import Any

import pytest

from scripts.collaboration.defect_ledger import DefectLedger, DefectState
from scripts.collaboration.dispatch_audit import DispatchAuditLogger
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.failure_taxonomy import EXIT_PRODUCT_FAILED, dispatch_exit_code
from scripts.collaboration.two_stage_review_gate import ReviewFinding, ReviewStage

pytestmark = pytest.mark.integration

_OK_CMD = f"{sys.executable} -c 'import sys; sys.exit(0)'"
_FAIL_CMD = f"{sys.executable} -c 'import sys; sys.exit(1)'"


class _OkBackend:
    """确定性本地 backend（无网络、无 API key）。"""

    model = "e2e-gate-fake-model"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, **kwargs: Any) -> str:
        return "Structured answer: 4"

    def generate_stream(self, prompt: str, **kwargs: Any):
        yield "Structured answer: 4"


class _FailBackend:
    """每次调用都失败的确定性本地 backend（C19 归为 product_failed）。"""

    model = "e2e-gate-fake-model"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, **kwargs: Any) -> str:
        raise RuntimeError("deterministic product failure")

    def generate_stream(self, prompt: str, **kwargs: Any):
        raise RuntimeError("deterministic product failure")
        yield ""  # pragma: no cover — generator formality


def _finding(category: str, severity: str = "critical", stage: ReviewStage = ReviewStage.CODE_QUALITY) -> dict:
    """真实 ReviewFinding 的落库形状。"""
    return ReviewFinding(
        stage=stage,
        severity=severity,
        category=category,
        description=f"review hit {category}",
        file_path="api/routes.py",
        line_range="42",
        suggestion=f"Review and fix {category}.",
    ).to_dict()


def _item(entry_id: str, command: str, description: str) -> dict[str, Any]:
    return {
        "id": entry_id,
        "description": description,
        "verify": {"kind": "command", "command": command},
    }


def _write_checklist(tmp_path, name: str, items: list[dict[str, Any]]) -> Any:
    checklist_path = tmp_path / name
    checklist_path.write_text(json.dumps({"schema_version": 1, "items": items}, indent=2), encoding="utf-8")
    return checklist_path


def _seed_defect(tmp_path) -> str:
    """在默认台账路径预登记一条 failure:product_failed 的 live 缺陷。

    W1 禁止凭空立案：先写一条真实 audit 事件，再按 signal_ref 立案。
    """
    db_path = tmp_path / "audit" / "seed.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE dispatch_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            user_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            details TEXT NOT NULL,
            prev_hash TEXT NOT NULL,
            entry_hash TEXT NOT NULL
        )
        """)
    conn.execute(
        "INSERT INTO dispatch_audit (event_type, user_id, timestamp, details, prev_hash, entry_hash)"
        " VALUES ('dispatch_end', 'tester', 1700000000.0, ?, '0', '0')",
        (json.dumps({"failure_class": "product_failed", "success": False}),),
    )
    conn.commit()
    conn.close()
    defect = DefectLedger(
        ledger_path=tmp_path / ".devsquad" / "defects.json",
        audit_db_path=db_path,
    ).add("audit:event=1&failure=product_failed", "seed defect for tracked-pass test")
    return defect.id


class TestE2EDispatchRegistrationGateIntegration:
    """端到端：dispatch → registration_gate → 阻止未登记信号"""

    def test_e2e_dispatch_failure_without_defect_ticket_rejected(self, tmp_path, monkeypatch):
        """
        端到端场景：dispatch失败 → findings写入 → registration_gate检测未登记 → 拒绝

        验证完整数据流：
        1. MultiAgentDispatcher.dispatch() 调用（确定性本地 backend，无网络）
        2. worker失败 → failure_class 写入 audit DB
        3. registration_gate Step 23.6 检测到未登记信号
        4. DispatchResult.success = False
        5. result.details["registration_gate"] 的 verdict="fail"
        """
        audit_path = tmp_path / "e2e_audit.db"
        # 默认台账路径（.devsquad/defects.json）从 CWD 解析，切到 tmp 避免污染仓库台账
        monkeypatch.chdir(tmp_path)

        disp = MultiAgentDispatcher(
            llm_backend=_FailBackend(),
            audit_db_path=str(audit_path),
            enable_memory=False,
            enable_registration_gate=True,
        )

        try:
            result = disp.dispatch(
                task_description="Implement secure authentication system", roles=["architect", "security"]
            )
        finally:
            disp.shutdown()

        # 验证：未登记的产品失败信号导致dispatch失败
        assert not result.success
        assert dispatch_exit_code(result) == EXIT_PRODUCT_FAILED

        # 验证：registration_gate出现在结果中且判定为fail
        gate_result = result.details["registration_gate"]
        assert gate_result["verdict"] == "fail"
        assert gate_result["signals"][0]["type"] == "failure:product_failed"
        assert gate_result["signals"][0]["status"] == "unregistered"
        assert result.details["failure_class"] == "product_failed"

        # 验证：audit DB中有记录，且带有立案依据（failure_class + gate结果）
        verifier = DispatchAuditLogger(audit_path)
        events = verifier.query(event_type="dispatch_end")
        assert len(events) == 1
        assert events[0].details["failure_class"] == "product_failed"
        assert events[0].details["registration_gate"]["verdict"] == "fail"
        verifier.close()

    def test_e2e_dispatch_with_tracked_defect_passes_gate(self, tmp_path, monkeypatch):
        """
        端到端场景：dispatch失败 + 已登记缺陷 → registration_gate放行

        验证三态判定：tracked状态（open/fixed）→ PASS
        """
        defect_id = _seed_defect(tmp_path)
        monkeypatch.chdir(tmp_path)

        disp = MultiAgentDispatcher(
            llm_backend=_FailBackend(),
            enable_memory=False,
            enable_registration_gate=True,
        )

        try:
            result = disp.dispatch(task_description="Review authentication module security", roles=["security"])
        finally:
            disp.shutdown()

        # 验证：即使dispatch失败，registration_gate应放行（因为已登记）
        # 注意：result.success仍为False（worker失败），但gate不阻止
        assert not result.success
        gate_result = result.details["registration_gate"]

        # 验证：gate判定为pass（tracked状态）
        assert gate_result["verdict"] == "pass"
        assert gate_result["signals"][0]["status"] == "tracked"
        assert gate_result["signals"][0]["tracked_by"] == [defect_id]
        assert not any("Registration gate blocked" in err for err in result.errors)


class TestE2EDispatchFeatureGateIntegration:
    """端到端：dispatch → feature_gate anchor/verify 完整周期"""

    def test_e2e_dispatch_feature_gate_anchor_verify_cycle(self, tmp_path):
        """
        端到端场景：Step 1 anchor → dispatch运行 → Step 23.5 verify

        验证：
        1. feature_gate.anchor() 在dispatch前（pre_steps）
        2. feature_gate.evaluate() 在dispatch后（Step 23.5）
        3. 结果包含现算覆盖矩阵（非worker自报）
        4. SHA256一致（无篡改）
        """
        checklist_path = _write_checklist(tmp_path, "e2e_checklist.json", [_item("AC1", _OK_CMD, "Core tests pass")])
        audit_path = tmp_path / "e2e_feature_audit.db"

        disp = MultiAgentDispatcher(
            llm_backend=_OkBackend(),
            audit_db_path=str(audit_path),
            enable_memory=False,
            enable_feature_gate=True,
            feature_gate_checklist=str(checklist_path),
            feature_gate_command_timeout_seconds=30,
        )

        try:
            result = disp.dispatch(task_description="Implement and test new feature", roles=["architect"])
        finally:
            disp.shutdown()

        # 验证：feature_gate结果出现在dispatch result中
        gate_result = result.details["feature_gate"]
        assert result.success
        assert gate_result["verdict"] == "pass"

        # 验证：包含anchor/verify双侧SHA256（64 位 hex）
        assert len(gate_result["anchored_sha256"]) == 64
        assert gate_result["anchored_sha256"] == gate_result["computed_sha256"]
        assert gate_result["checklist_path"] == str(checklist_path.resolve())

        # 验证：覆盖矩阵来自真实命令执行
        coverage = gate_result["entries"]
        assert len(coverage) > 0
        assert coverage[0]["id"] == "AC1"
        assert coverage[0]["status"] in ["pass", "fail", "waived"]
        assert coverage[0]["exit_code"] == 0

        # 验证：audit事件携带双哈希证据
        verifier = DispatchAuditLogger(audit_path)
        events = verifier.query(event_type="dispatch_end")
        assert events[0].details["feature_gate"]["anchored_sha256"] == gate_result["anchored_sha256"]
        verifier.close()

    def test_e2e_feature_gate_failure_blocks_dispatch(self, tmp_path):
        """
        端到端场景：feature_gate验证失败 → dispatch success=False

        验证gate失败会正确传播到dispatch结果
        """
        checklist_path = _write_checklist(
            tmp_path, "e2e_failing_checklist.json", [_item("FAIL1", _FAIL_CMD, "This test will fail")]
        )
        audit_path = tmp_path / "e2e_fail_audit.db"

        disp = MultiAgentDispatcher(
            llm_backend=_OkBackend(),
            audit_db_path=str(audit_path),
            enable_memory=False,
            enable_feature_gate=True,
            feature_gate_checklist=str(checklist_path),
            feature_gate_command_timeout_seconds=30,
        )

        try:
            result = disp.dispatch(task_description="Feature that fails acceptance", roles=["architect"])
        finally:
            disp.shutdown()

        # 验证：feature_gate失败导致dispatch失败
        assert not result.success

        # 验证：feature_gate结果反映失败
        gate_result = result.details["feature_gate"]
        assert gate_result["verdict"] == "fail"
        assert gate_result["entries"][0]["status"] == "fail"

        # 验证：错误传播到result.errors（gap 明细）
        assert len(result.errors) > 0
        assert any("Feature gate gap: FAIL1" in str(err) for err in result.errors)
        assert result.details["failure_class"] == "product_failed"
        assert dispatch_exit_code(result) == EXIT_PRODUCT_FAILED


class TestE2EDispatchGateCombinedIntegration:
    """端到端：registration_gate + feature_gate 联合场景"""

    def test_e2e_both_gates_enabled_comprehensive_check(self, tmp_path, monkeypatch):
        """
        端到端场景：同时启用两个gate → 验证Step编排正确

        验证：
        1. Step 1: feature_gate anchor
        2. Step 8-22: dispatch执行
        3. Step 23.5: feature_gate evaluate
        4. Step 23.6: registration_gate evaluate
        5. Step 24: failure_class终态重算
        """
        checklist_path = _write_checklist(tmp_path, "combined_checklist.json", [_item("T1", _OK_CMD, "Basic check")])
        audit_path = tmp_path / "combined_audit.db"
        monkeypatch.chdir(tmp_path)  # registration gate 的默认台账路径

        disp = MultiAgentDispatcher(
            llm_backend=_OkBackend(),
            audit_db_path=str(audit_path),
            enable_memory=False,
            enable_feature_gate=True,
            feature_gate_checklist=str(checklist_path),
            feature_gate_command_timeout_seconds=30,
            enable_registration_gate=True,
        )

        try:
            result = disp.dispatch(task_description="Comprehensive gate test", roles=["architect"])
        finally:
            disp.shutdown()

        # 验证：两个gate都出现在结果中
        assert "feature_gate" in result.details
        assert "registration_gate" in result.details

        # 验证：feature_gate先执行（Step 23.5）并给出双哈希 + 现算矩阵
        feature_gate = result.details["feature_gate"]
        assert feature_gate["verdict"] == "pass"
        assert feature_gate["anchored_sha256"] == feature_gate["computed_sha256"]
        assert len(feature_gate["entries"]) == 1

        # 验证：registration_gate后执行（Step 23.6），本次run无强制信号
        reg_gate = result.details["registration_gate"]
        assert reg_gate["verdict"] == "pass"
        assert reg_gate["signals"] == []

        # 验证：failure_class终态（Step 24）
        assert result.details["failure_class"] == "none"
        assert result.success

        # 验证：audit DB包含完整事件（带两个gate结果）
        verifier = DispatchAuditLogger(audit_path)
        events = verifier.query(event_type="dispatch_end")
        latest = events[0].details
        assert latest["feature_gate"]["verdict"] == "pass"
        assert latest["registration_gate"]["verdict"] == "pass"
        verifier.close()

    def test_e2e_disabled_gates_zero_trace(self, tmp_path):
        """
        端到端场景：两个gate都禁用 → 零痕迹（五面验证）

        验证PRD §9：台账默认关闭，4.8.x行为字节一致
        """
        audit = DispatchAuditLogger()

        # 默认配置（两个gate都禁用）
        disp = MultiAgentDispatcher(
            llm_backend=_OkBackend(),
            audit_logger=audit,
            enable_memory=False,
            enable_feature_gate=False,
            enable_registration_gate=False,
        )

        try:
            result = disp.dispatch(task_description="Test with gates disabled", roles=["architect"])
        finally:
            disp.shutdown()

        # 验证：五面零痕迹
        # 1. details中无gate字段
        assert "feature_gate" not in result.details
        assert "registration_gate" not in result.details

        # 2. result属性与to_dict中无gate
        assert result.feature_gate is None
        assert result.registration_gate is None
        assert result.to_dict()["feature_gate"] is None
        assert result.to_dict()["registration_gate"] is None

        # 3. Markdown报告中无gate章节
        markdown = result.to_markdown()
        assert "Feature gate" not in markdown
        assert "Registration gate" not in markdown

        # 4. audit事件中无gate字段
        events = audit.query(event_type="dispatch_end")
        assert len(events) == 1
        assert "feature_gate" not in events[0].details
        assert "registration_gate" not in events[0].details

        # 5. success不受gate影响（完全4.8.x行为）
        assert result.success


class TestE2EDefectCLISubprocessIntegration:
    """端到端：CLI subprocess测试，验证CLI命令与API行为一致"""

    def test_cli_defect_add_list_workflow(self, tmp_path):
        """
        CLI subprocess场景：devsquad defect add → list → update → close

        验证：
        1. CLI命令正确调用DefectLedger API
        2. 参数解析正确（--signal-ref, --summary, --json）
        3. JSON输出格式可解析
        """
        ledger_path = tmp_path / "cli_defects.json"
        audit_path = tmp_path / "cli_audit.db"

        # 准备真实audit DB：事件1 = 带findings的失败跑，事件2 = 干净回归跑
        logger = DispatchAuditLogger(audit_path)
        logger.log_dispatch_end(
            user_id="run1",
            success=False,
            duration=1.0,
            findings=[_finding("VULN-1")],
            failure_class="product_failed",
        )
        logger.log_dispatch_end(user_id="verify", success=True, duration=1.0, failure_class="none")
        logger.close()

        # Step 1: CLI add
        add_proc = subprocess.run(
            [
                sys.executable,
                "scripts/cli.py",
                "defect",
                "add",
                "--signal-ref",
                "audit:event=1&finding=0",
                "--summary",
                "CLI test defect",
                "--ledger-path",
                str(ledger_path),
                "--audit-db-path",
                str(audit_path),
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert add_proc.returncode == 0, f"CLI add failed: {add_proc.stderr}"
        add_output = json.loads(add_proc.stdout.strip())
        assert add_output["id"].startswith("DEF-")
        assert add_output["state"] == "open"
        assert add_output["signal"]["ref"] == "audit:event=1&finding=0"
        defect_id = add_output["id"]

        # Step 2: CLI list（--json 输出整个数组）
        list_proc = subprocess.run(
            [
                sys.executable,
                "scripts/cli.py",
                "defect",
                "list",
                "--ledger-path",
                str(ledger_path),
                "--audit-db-path",
                str(audit_path),
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert list_proc.returncode == 0, f"CLI list failed: {list_proc.stderr}"
        list_output = json.loads(list_proc.stdout.strip())
        assert len(list_output) == 1
        assert list_output[0]["id"] == defect_id

        # Step 3: CLI update（标记为fixed）
        update_proc = subprocess.run(
            [
                sys.executable,
                "scripts/cli.py",
                "defect",
                "update",
                defect_id,
                "--commit",
                "abc123",
                "--summary",
                "Fixed by commit abc123",
                "--ledger-path",
                str(ledger_path),
                "--audit-db-path",
                str(audit_path),
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert update_proc.returncode == 0, f"CLI update failed: {update_proc.stderr}"
        update_output = json.loads(update_proc.stdout.strip())
        assert update_output["state"] == "fixed"
        assert update_output["fix"]["commit"] == "abc123"

        # Step 4: CLI close（run-ref 必须指向真实、干净的回归事件）
        close_proc = subprocess.run(
            [
                sys.executable,
                "scripts/cli.py",
                "defect",
                "close",
                defect_id,
                "--run-ref",
                "audit:event=2",
                "--ledger-path",
                str(ledger_path),
                "--audit-db-path",
                str(audit_path),
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert close_proc.returncode == 0, f"CLI close failed: {close_proc.stderr}"
        close_output = json.loads(close_proc.stdout.strip())
        assert close_output["state"] == "closed"
        assert close_output["regression"]["run_ref"] == "audit:event=2"

    def test_cli_defect_error_exit_codes(self, tmp_path):
        """
        CLI错误场景：验证C19退出码约定

        - 0: 成功
        - 1: 产品失败（状态机违规、验证失败）
        - 2: 环境阻塞（ledger I/O、audit DB不可达 — OSError/sqlite3.Error）
        """
        ledger_path = tmp_path / "error_defects.json"
        audit_path = tmp_path / "error_audit.db"

        # 场景1：产品失败（状态机违规：update不存在的defect）
        update_proc = subprocess.run(
            [
                sys.executable,
                "scripts/cli.py",
                "defect",
                "update",
                "DEF-999999",
                "--commit",
                "abc",
                "--summary",
                "not a real defect",
                "--ledger-path",
                str(ledger_path),
                "--audit-db-path",
                str(audit_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert update_proc.returncode == 1
        assert "not found" in update_proc.stderr.lower()

        # 场景2：signal_ref 无法解析（audit DB 不存在 → 拒绝立案）
        nonexist_audit = tmp_path / "nonexist_audit.db"
        add_proc = subprocess.run(
            [
                sys.executable,
                "scripts/cli.py",
                "defect",
                "add",
                "--signal-ref",
                "audit:event=1&finding=0",
                "--summary",
                "Test",
                "--ledger-path",
                str(ledger_path),
                "--audit-db-path",
                str(nonexist_audit),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert add_proc.returncode == 1
        assert "audit db not found" in add_proc.stderr.lower()


class TestE2ECrossRunTimestampIntegration:
    """端到端：跨run timestamp/task_id关联测试"""

    def test_multi_run_defect_tracking_with_timestamps(self, tmp_path):
        """
        跨run场景：多次run → 每次run有独立timestamp/user_id → signal_ref准确关联

        验证：
        1. Run 1: 发现缺陷 → audit event 2 (timestamp T1)
        2. Run 2: 修复缺陷 → audit event 4 (timestamp T2 > T1)
        3. Run 3: 验证修复 → audit event 6 (timestamp T3 > T2)
        4. signal_ref包含正确的event ID关联
        5. timestamp递增，可追溯完整生命周期
        """
        audit_path = tmp_path / "cross_run_audit.db"
        ledger_path = tmp_path / "cross_run_defects.json"

        logger = DispatchAuditLogger(audit_path)

        # Run 1: 发现缺陷（事件 1 = start，事件 2 = end）
        logger.log_dispatch_start("run1", "Run 1: Initial test", ["architect"])
        logger.log_dispatch_end(
            user_id="run1",
            success=False,
            duration=1.0,
            findings=[_finding("BREAK-1")],
            failure_class="product_failed",
        )
        defect = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path).add(
            "audit:event=2&finding=0", "Issue discovered in Run 1"
        )
        run1_event_id = 2

        time.sleep(0.01)

        # Run 2: 模拟修复（标记defect为fixed）
        logger.log_dispatch_start("run2", "Run 2: Fix applied", ["architect"])
        logger.log_dispatch_end(user_id="run2", success=True, duration=1.5, failure_class="none")
        ledger = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        ledger.update(defect.id, "fix-commit-123", "Fixed in Run 2")

        time.sleep(0.01)

        # Run 3: 验证修复（用干净的回归事件关闭缺陷）
        logger.log_dispatch_start("run3", "Run 3: Verification", ["architect"])
        logger.log_dispatch_end(user_id="run3", success=True, duration=0.8, failure_class="none")
        ledger.close(defect.id, "audit:event=6")
        logger.close()

        # 验证：跨run timestamp顺序（query 返回新→旧，反转成时间顺序）
        verifier = DispatchAuditLogger(audit_path)
        dispatch_end_events = list(reversed(verifier.query(event_type="dispatch_end", limit=100)))
        assert len(dispatch_end_events) == 3

        t1, t2, t3 = [event.timestamp for event in dispatch_end_events]
        assert t1 < t2 < t3, "Timestamp should be strictly increasing across runs"

        # 验证：user_id区分不同run
        assert [event.user_id for event in dispatch_end_events] == ["run1", "run2", "run3"]

        # 验证：defect完整生命周期可追溯
        final_defect = ledger.list_defects()[0]
        assert final_defect.state is DefectState.CLOSED
        assert final_defect.signal["ref"] == "audit:event=2&finding=0"

        # 验证：可以从signal_ref反查原始audit event，且其timestamp最早
        original_event_id = int(final_defect.signal["ref"].split("event=")[1].split("&")[0])
        assert original_event_id == run1_event_id
        conn = sqlite3.connect(str(audit_path))
        row = conn.execute("SELECT timestamp FROM dispatch_audit WHERE id = ?", (original_event_id,)).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == t1

    def test_concurrent_run_timestamp_uniqueness(self, tmp_path):
        """
        并发场景：快速连续dispatch → 验证timestamp/hash唯一性

        验证audit chain完整性（每个entry的prev_hash正确链接）
        """
        audit_path = tmp_path / "concurrent_audit.db"

        # 快速连续执行5次dispatch
        for i in range(5):
            disp = MultiAgentDispatcher(
                llm_backend=_OkBackend(),
                audit_db_path=str(audit_path),
                enable_memory=False,
            )

            try:
                disp.dispatch(task_description=f"Concurrent run {i + 1}", roles=["architect"])
            finally:
                disp.shutdown()

            time.sleep(0.001)  # 极小间隔，测试timestamp精度

        logger = DispatchAuditLogger(audit_path)

        # 验证：链完整、无篡改
        assert logger.verify_chain() is True
        assert logger.detect_tamper() == []

        events = logger.get_entries(limit=100)  # 新→旧
        assert len(events) >= 10  # 5 runs × (start + end)

        # 验证：所有events的timestamp唯一
        timestamps = [event.timestamp for event in events]
        assert len(timestamps) == len(set(timestamps)), "All timestamps should be unique"

        # 验证：entry_hash唯一
        hashes = [event.entry_hash for event in events]
        assert len(hashes) == len(set(hashes)), "All entry hashes should be unique"

        # 验证：chain正确（新→旧顺序下，前一条的prev_hash = 后一条的entry_hash）
        for i in range(1, len(events)):
            assert events[i - 1].prev_hash == events[i].entry_hash, f"Chain broken at index {i}: prev_hash mismatch"

        # 验证：timestamp严格单调（新→旧 = 递减）
        for i in range(1, len(timestamps)):
            assert timestamps[i] <= timestamps[i - 1], f"Timestamp not monotonic at index {i}"

        # 验证：原始DB中按 id 升序的链也连续（prev_hash 指向上一行）
        conn = sqlite3.connect(str(audit_path))
        rows = conn.execute("SELECT prev_hash, entry_hash FROM dispatch_audit ORDER BY id ASC").fetchall()
        conn.close()
        for prev_row, curr_row in zip(rows, rows[1:]):
            assert curr_row[0] == prev_row[1], "DB chain broken: prev_hash mismatch"
