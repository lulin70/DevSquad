# DevSquad V4.5.12 Release Notes

> **发布日期**: 2026-08-31　**Tag**: `v4.5.12`　**基线**: v4.5.11 (`8ee1db0`)

## 概要

V4.5.12 一次发版关闭 V4.5.11+ 全部三项 backlog（用户裁决：全部三项一次发版）：

1. **TRAE IDE 3.3.95 真实监听方联调**：建立 5 trace 真实联调证据框架（`docs/e2e_evidence/V4.5.12_trae_ide_real/`），覆盖 weiransoft v2.8.4 协议全部 v2 特性（marker 7 字段 / prompt_file / subagent_type 映射 / fuse / 资源上限 / 跨版本隔离 / v1 强制回退）。trace 为人工采集证据，发布门禁要求框架就位，真实采集在 TRAE IDE 环境完成后归档。
2. **SQLite 重立项条件监控**（stats + Prometheus alert 双轨）：`RiskStoreStats` 4 信号埋点 + `risks stats` CLI + `devsquad_v4512_risk_store_*` 4 metrics + 4 条 alert 规则 + 4 个 RUNBOOK 场景。**SQLite 裁决维持 JSON-only long-term**，告警仅触发人工重立项评估。
3. **`--severity` 完全退役**（Breaking）：`risks list/show/export --severity` 移除，argparse 直接拒绝（exit 2）。迁移：数值过滤 → `--min-exposure`；字符串过滤 → `--category`。

命名澄清（本轮消除歧义）："v2.8.4" 指 weiransoft/TraeMultiAgentSkill 协议参考项目版本；本地联调对象是 TRAE IDE 3.3.95。两者版本号独立。

## 新增

- `RiskStoreStats`（`file_risk_store.py`）：`capacity` / `concurrent_writes_1m`（60s 滑动窗口）/ `cross_host_lock_signals` / `slow_query_signals`（>50ms）
- `risks stats --format text|json` 子命令（只读）
- `devsquad_v4512_risk_store_capacity/concurrent_writes/cross_host_signals/slow_queries` metrics（含无 prometheus_client 的直读 fallback）
- ALERT_RULES 4 条规则：`RiskStoreCapacityHigh`（critical）/ `RiskStoreConcurrentWriteHigh`（warning）/ `RiskStoreCrossHostSignal`（critical）/ `RiskStoreSlowQueryHigh`（warning）
- RUNBOOK §V4.5.12-A/B/C/D 4 个 incident 场景
- anti-ghost 新增 2 计数器：`RiskStoreStats_V4512.1` + `RisksStatsCli_V4512.2`（27/27 PASS）

## 变更

- **Breaking**：`--severity` 移除。`risks list/show/export --severity 0.5` → `unrecognized arguments` exit 2
- `devsquad metrics` JSON version 字段 V4.5.2 → V4.5.12（清单扩展至 v452+v4512 全量）

## 门禁与验证

- ruff 0 errors（scripts/ + tests/）
- anti-ghost 27/27 PASS（含 2 个 V4.5.12 新计数器）
- 新增测试 23 passed（4 文件：stats 单元 / severity 退役单元 / 信号集成 / stats+metrics E2E）
- 全量回归 `pytest -m "not external"`：9516 passed / 2 failed（`test_cli_metrics` version 断言）→ 按新契约更新断言后 16 passed；受影响套件重跑全绿
- 版本一致性：代码 + 文档 + 4 层 TRAE 缓存同步 4.5.12

## 已知限制

- TRAE IDE 3.3.95 真实联调 5 trace 为人工采集，需在真实 IDE 环境完成归档后勾选（模板与采集方法已就位）
- SQLite risk store 维持 JSON-only long-term 裁决；4 条告警触发后由人工启动重立项评估
