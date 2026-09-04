# DevSquad V4.5.13 Release Notes

> **发布日期**: 2026-08-31　**Tag**: `v4.5.13`　**基线**: v4.5.12 (`9940ac6`)

## 概要

V4.5.13 关闭 V4.5.12+ backlog 三项（工具化 + 可观测性硬化；无 Breaking）：

1. **TRAE IDE 联调采集工具化**：`scripts/collect_trae_traces.py` 一键采集 5 trace，三态诚实状态契约（`success | timeout | fail_closed`），timeout = 监听方不在线的有效证据，不得伪造 PASS。
2. **跨主机信号自动化**：`FileRiskStore` 通过 `statvfs ST_REMOTE`（平台安全降级）与远程语义 errno（`ESTALE/EREMOTE/EBADRPC`）自动记录 `cross_host_lock_signals`；本地 `EAGAIN` 竞争不误报。
3. **/metrics 暴露**：`devsquad_v4512_risk_store_*` 序列经 `record_risk_store_stats()`（delta 导出）接入 FastAPI `/metrics`。

另含环境治理：devsquad 技能缓存**单一来源收敛**（用户裁决方案 A），修复 "/" 面板重复与注册索引缺失。

## 新增

- `scripts/collect_trae_traces.py`（`--trace N|--all --wait-seconds --dry-run`）
- `DevSquadMetrics.record_risk_store_stats()` + 4 个 `/metrics` 序列
- 跨主机自动信号（`_looks_like_remote_fs` + `_REMOTE_ERRNOS`）

## 变更

- counter 指标名显式 `_total` 后缀（对齐 prometheus_client exposition 归一化），ALERT_RULES / metrics CLI 清单同步
- `check_version_consistency.py` 技能缓存层检查适配单一来源策略（其余层 optional SKIP）

## 门禁与验证

- ruff 0；新增测试 18（cross-host 单元 5 + trace collector 单元 7 + /metrics 集成 4 + 冒烟 1 + 兼容 1）
- 全量回归 `pytest -m "not external"`：9535 passed / 1 failed（`test_concurrent_dispatch_stability` 并发压测时序性失败，与本迭代改动零调用关系；单跑 + 全文件重跑 6/6 绿确认）
- 采集脚本 dry-run 验证 5 场景计划
- 版本一致性 4.5.13 全绿（技能单一来源层校验）

## 已知限制

- trace 实际 PASS 归档仍需在 TRAE IDE 3.3.95 监听方在线时执行采集脚本（timeout 证据可先行归档）
- Prometheus 服务器端到端抓取 / promtool 规则校验留待部署环境（backlog）
- `~/.trae-cn/skills` 第三方 pack 平铺污染未清理（backlog，需用户确认范围）
