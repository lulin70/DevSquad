# DevSquad V4.5.15 Release Notes

> **发布日期**: 2026-09-02　**Tag**: `v4.5.15`　**基线**: v4.5.14 (`5ce4b6d`)

## 定位

PATCH 版本（SemVer 合规）：无新用户功能、无 Breaking。
PRD: `docs/prd/V4.5.15_PRD.md`。

## 交付内容

### 1. 根因修复：SKILL.md frontmatter YAML 解析失败（"/" 面板问题的真正根因）

`description: |` 块内第 16 行（V4.5.11 历史条目）顶格书写，破坏 YAML block
scalar；配合后续裸冒号行，`yaml.safe_load` 抛 `ScannerError` → TRAE 从未注册
devsquad → "/" 面板看不到 DevSquad。这是 V4.5.13 诊断的漏网根因（当时只治理
了重复副本与索引，未验证 frontmatter 可解析性）。

修复：源文件 + 各缓存层同步修正；`check_version_consistency.py` 新增
**frontmatter YAML 可解析 + name/slug/version/description 必填键**阻塞门禁
（防止回归）。

### 2. skills-index.json 注册机制核实（backlog 关闭）

- 全盘唯一的 `~/.trae-cn/skills/skills-index.json` 只是 trae-multi-agent 技能包
  的自述安装清单，**不是 TRAE 注册表**，与 devsquad 注册无关。
- 真实注册链路：注册单元 = 各技能 SKILL.md frontmatter；实际读取层 = 工作区根
  `<工作区根>/.trae/skills/`（2026-07-27 实证 + 本次复核一致）；启停由
  `skill-config.json` 管理；内置技能走 `builtin/manifests/*.json` + CDN。
- CLAUDE.md 缓存层章节已按此结论修正。

### 3. Prometheus 端到端抓取工具（真实运行延后）

- 新增 `scripts/verify_prometheus_e2e.py`，三态诚实契约 `pass | fail |
  tool_missing`（不伪造 PASS）。链路：真实 `DevSquadMetrics.record_risk_store_stats`
  → HTTP exposition → `promtool check metrics`（格式 lint）→ `promtool check
  config` → Prometheus 1s 抓取 → `/api/v1/query` 非空样本 → 进程与临时目录清理。
- +7 单元测试（binary 探测、config 生成、exposition 记录、tool_missing 契约）。
- **用户裁决（2026-09-02）**：真实 E2E 运行与 brew 安装延后；后续执行
  `python3 scripts/verify_prometheus_e2e.py` 并归档
  `docs/e2e_evidence/V4.5.15_prometheus_e2e/` 即可补齐证据。

### 4. 用户裁决登记

- `~/.trae-cn/skills` pack（trae-multi-agent 平铺结构）**不清理**，
  backlog "pack 平铺清理" 关闭。
- devsquad pack **同步全部三层**：L1 `~/.trae-cn/skills/devsquad/` +
  L2 `~/.trae/skills/devsquad/` + L3 工作区根 `.trae/skills/devsquad/`
  （推翻 V4.5.13 单源策略；面板重复风险知情接受）。

## 门禁

- ruff：0 error
- 测试：新增 11（T14 frontmatter 门禁 4 + prometheus e2e 7）；
  全量回归 `not external` 0 failed
- 版本一致性：`check_version_consistency.py` 4.5.15 全绿（含三层缓存
  版本 + 字节级内容比对 + frontmatter 门禁）

## 升级与回滚

无 API/配置变更；从 v4.5.14 直接拉取即可。如需回滚，`git checkout v4.5.14`。
