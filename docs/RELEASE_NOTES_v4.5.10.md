# DevSquad V4.5.10 Release Notes

> **发布日期**: 2026-08-30  
> **版本类型**: MINOR（SemVer 合规）  
> **基线**: V4.5.9（commit `4f954a2` / tag `v4.5.9`）

## 主题

**HostLLMBridge v2 生产接线 + `--async` CLI + 文档收敛**。关闭 V4.5.9 审计确认的两个发布阻塞缺口：v2 协议已实现但未接入生产 factory，CLI 无显式异步入口。

## 核心交付

| 项 | 内容 |
|---|---|
| G-α 生产接线 | `create_backend("host"/"auto"/"auto-fallback")` 默认返回 `HostBridgeBackendV2`；显式 `host-v1`/`host-v2`；flag fail-closed |
| G-β prompt 分离 | v2 request JSON 不再内嵌 prompt；`prompt_file` 为唯一 canonical 来源；兼容读取历史 inline 格式 |
| G-θ 完全隔离 | v1 `logs/host_llm_bridge/v1/protocol.marker`，v2 `.../v2/protocol.v2.marker`；v2 不再迁移/触碰 v1 文件 |
| G-δ v2 E2E | FakeHostRunnerV2 真实子进程 round-trip：success/failure/timeout + factory 全链路 + 跨版本隔离 |
| P2-2 `--async` | CLI `--async`/`--no-async` 三态互斥；优先级 flag > env > sync；真实调用路径 spy + 子进程 E2E 双证明 |
| 裁决落档 | P2-1 SQLite 正式 JSON-only long-term（PRD §6）；P2-2 交付 |

## 安全硬化（v2 协议）

- marker 严格 7 字段 schema：缺字段/多字段/类型错误/越界路径全部 fail-closed 拒绝
- 路径安全：realpath canonical + commonpath + `O_NOFOLLOW`（拒绝 symlink）+ fstat regular-file（TOCTOU 打开时复核）
- 权限：目录 `0700`、文件 `0600` 强制
- 资源上限：prompt 512 KB / request JSON 256 KB / response 4 MB，超限 fail-closed 不留半成品

## 真实缺陷修复

- `_execute_async_workers` 在 mock 模式（`llm_backend=None`）下抛未捕获 `ValueError: Unknown backend type: NoneType`，导致 `DEVSQUAD_USE_ASYNC=1` 的 CLI 路径必败；现以 `"mock"` 名解析并优雅降级
- `create_backend("host")` 显式路径未透传 `timeout_seconds`

## 行为变化（Breaking / Notice）

1. `host`/`auto`/`auto-fallback` 默认走 v2 协议。v1 使用方：`export DEVSQUAD_HOST_BRIDGE_VERSION=v1` 或 `DEVSQUAD_V455_DISABLE_HOST_BRIDGE_V2=1`
2. v1 默认目录迁移至 `logs/host_llm_bridge/v1/`（旧目录不迁移不删除）
3. v2 request JSON 不含 inline prompt（上游 v2.8.4 监听方按 `prompt_file` 读取）
4. v2 reader 拒绝 v1 格式 marker（fail-closed）

## 门禁与验证

- PRD 三贤者复审：架构 8.7 / 测试 8.6 / 安全 8.6（≥8.5 门禁）
- 单元 + 契约 120 passed（含既有 v1 测试零修改）；E2E 19 passed（v2 subprocess round-trip 8 + CLI journey 5 + v1 E2E 6）
- anti-ghost 25/25 PASS（新增 wiring 层 `HostBridgeV2Wiring_V4510.1`）
- ruff 全清洁；版本一致性检查通过（详见发布流程输出）
- 全量回归 `pytest -m "not external"`：见发布流程最终输出
- 真实用户旅程（PRD §4.5）：sync 默认 / `--async` / `--no-async` 覆盖 env / `DEVSQUAD_HOST_BRIDGE_VERSION=v1` 显式回退 / v2 子进程 round-trip

## 文档收敛清单（P1-1 / P1-2 / P2-4 / P2-5 / P3-2 / P3-3 / P3-4）

- 运维：ALERT_RULES（v2 wiring/timeout 告警）、RUNBOOK（§V4.5.10-A/B/C）、ROLLBACK（R1 v2→v1 flag 回退 / R2 async→sync / R3 全量回滚）
- 对外：PROJECT_STATUS、README×3、SKILL.md、skill-manifest、Dockerfile、helm Chart 同步 4.5.10
- 技术债：TECH_DEBT 更新（SQLite 裁决关闭、顺延项登记）；异常处理指南重写为 V4.5.x 现状；性能监控文档状态对齐
- 归档：`ROADMAP_v4.5.x_P12.md` → `_archive/ROADMAP_v4.5.x_P12_SUPERSEDED.md`（原位置留指针）；V4.4.2 Kanban 评估正式关闭；SmartConfirmation 条目关闭

## 已知限制

- `_LegacyRiskStoreProxy` 删除顺延至专门清理迭代
- `Worker.execute`/`aexecute` 合并评估、risks CLI 输出风格统一保持 P3 backlog
- 网络 listener / 远程信任模型不在本版范围（PRD §3.6）
