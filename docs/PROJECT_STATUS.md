# DevSquad 项目状态

> **代码版本**: V4.8.1（F-D1 修复 PATCH，PR #62/#63/#65/#67；版本一致性门禁 82/82 全绿 2026-10-22 本地实测，TRAE 四层缓存已同步 8/8）
> **发布状态**: V4.8.1 **已发布**（2026-10-24：升版 PR #63 squash merge `2d03bb5` → 首次 tag 触发 release run 39934219953 于 pip-audit 硬门失败——black 26.5.1 新披露 CVE-2026-114134（v4.8.0→4.8.1 时间窗内）；修复 PR #65（black 26.10.1 三副本 + pyproject dev extra 第四副本、pillow 13.0.0、filelock 4.2.4、streamlit 1.66.1 resolver 一致性）squash merge `0d2b7ba` → 删 tag 重打 → release.yml [run 40050464796](https://github.com/lulin70/DevSquad/actions/runs/40050464796) 全绿 → PyPI 4.8.1 + GitHub Release v4.8.1；干净房安装 + F-D1 行为探针通过，见"最新评估"）。
> **最后更新**: 2026-10-24
> **最新评估**: P1 工作流进场批完成（执行依据：[2026-10-20_value_proposal_execution_plan.md](planning/2026-10-20_value_proposition_execution_plan.md) §5，PRD：[V4.8.0_workflow-entry_PRD.md](prd/V4.8.0_workflow-entry_PRD.md)）：P1-R1 devsquad-gate 可复用 workflow + diff 通道模式接线（PR #50）；P1-R2 三画像通道 QUICKSTART 重写 + init 后端分流 + doc_command 门禁 36 条（PR #54）；P1-R3 dogfooding 季度报告生成器 + 首期 2026-Q4 报告（PR #53）；P1-R4 MCP 集成指南单一事实源 + stdio e2e 证据（PR #52）；TD-076 mcp 约束收紧 `>=1,<2`（PR #55）；P1-E1 消费者审计六项裁定（PR #58/#56）；版本升 4.8.0 全量 bump（PR #59）；P1 closeout（PR #61）。R1 验收①外部试装两段式（zeroclaw STAGE1 机制面 run 39734750597 抓到 F-1/F-2 当日修复；STAGE2 findings 面 run 39738128709 注入反模式 → BREAK 2 → fail → exit 1，T-4/T-5 同场）。T-2 dogfood（PR #60，run 39739886471）。**4.8.1 F-D1 修复 PATCH 已发布**（设计 §7.4 rev2，dogfood 第三个真实发现）：修复三件套 = `rule_engine.matches()` 尾部 `/**` gitignore 语义（同修 W1-3 嵌套排除洞）+ `diff_pattern_scanner.filter_diff_pattern_findings()` 族分治（secrets 查一切保留路径、代码气味限 source 类）+ CLI 接线同参（PR #62，新增单测 14 例，全量回归 10171 passed/24 skipped）；升版 PR #63（版本链 82/82 + gate.yml pin 4.8.1 + TRAE 缓存 + CHANGELOG/VERSION_HISTORY，dogfood gate 在升版 PR 上 pass 0 findings）；发布链一次失败重跑：black 26.5.1 CVE-2026-114134 时间窗披露 → PR #65 升锁（black 26.10.1 全部四副本、pillow 13.0.0、filelock 4.2.4、streamlit 1.66.1）→ tag 重打 `0d2b7ba` → run 40050464796 全绿；发布后验证：干净房 `DevSquad 4.8.1` + F-D1 行为探针（.md 代码气味被 source 门挡下、.py 报 BREAK-2）+ wrapper 升 `@v4.8.1` dogfood 复验 pass 0 findings（PR #67，run 40063417455）——F-D1 修复生产闭环完成。
> **硬约束状态**: Ruff lint/format、mypy（scripts/+skills/ 0 errors）、版本一致性（82/82，2026-10-22 本地实测，含 stale-string 负向门禁）、配置一致性（7/7，含 doc_command 36 条）、Bandit（0 HIGH/0 MEDIUM）、pip-audit（runtime requirements.lock 严格审计无已知漏洞；dev lock 2026-10-24 升级后双面全净——black 26.10.1/pillow 13.0.0/filelock 4.2.4/streamlit 1.66.1，原 TD-075 Pillow 豁免已随本批解除）、测试质量门（0 MAJOR）本地已通过；权威结果以 GitHub Actions 为准。性能基线 mock + api 路径已真实测量（2026-10-20，P0-W3）；host 路径仍为诚实 stub（TD-071，需 TRAE IDE 会话环境重测）。
> **PyPI**: 最新发布版本为 [4.8.1](https://pypi.org/project/devsquad/4.8.1/)（2026-10-24 发布后实测；采集命令：`curl -s https://pypi.org/pypi/devsquad/json | jq -r '.info.version'`，输出 4.8.1）。干净房安装实测：`pip install devsquad==4.8.1 --index-url https://pypi.org/simple/` → `devsquad --version` 输出 `DevSquad 4.8.1`；F-D1 行为探针通过（.md 代码气味被 source 门挡下、.py 报 BREAK-2，族分治随产物生效）；注意本机默认清华镜像有同步滞后，实测须指 `--index-url https://pypi.org/simple/`。
> **GitHub Release**: 最新为 [DevSquad v4.8.1](https://github.com/lulin70/DevSquad/releases/tag/v4.8.1)（发布于 2026-10-24T01:42:31Z，`gh release view v4.8.1` 实测；assets：`devsquad-4.8.1-py3-none-any.whl` + `devsquad-4.8.1.tar.gz`）；历史 release 状态请查看 [GitHub Releases](https://github.com/lulin70/DevSquad/releases)。

---

## 1. 项目概述

DevSquad 是一个多角色 AI 任务编排器。任务提交后，系统按任务匹配专业角色，使用当前同步/异步 Worker 路径执行，经过共享上下文和共识处理后生成结构化报告。

**核心定位**: User Task → [InputValidator] → [RoleMatcher] → [Coordinator] → [Sync/Async Workers] → [Scratchpad 共享] → [ConsensusEngine] → [Report]

---

## 2. 模块清单

**模块数**: 219 个公开核心模块（`scripts/collaboration/` 下的当前统计；文档 headline 允许小幅漂移，详见 [SKILL.md](../SKILL.md) Architecture Overview）

**V4.5.16 PATCH（Housekeeping + Digital Truth，无新用户功能）**:
- `_version_info` 元组对齐 `(4,5,16)` + `__version__` 字符串；helm chart `image.tag` 与 `Chart.yaml` 同步；`scripts/publish_now.sh` 归档 `docs/_archive/scripts/`；`scripts/check_module_activation.py` 显式覆盖 8 个新 counter；`tests/unit/test_v4515_prometheus_e2e.py` 迁 `tests/e2e/` 并加 `@pytest.mark.e2e/slow`；`docs/release_notes/` 命名空间统一（11 份 git mv）；`scripts/api/routes/{dispatch,lifecycle,metrics_gates}.py` 14 处 `logger.error(..., exc_info=True)` 收紧为 `logger.exception`；`scripts/sync_skill_pack.py` 上线 + 7 测试；18 个 SSOT 文件版本统一到 4.5.16；`DevSQuad → DevSquad` 8 活文件 16 行；`docs/prd/V4.5.14_PRD.md` 与 `V4.5.16_PRD.md` 补全；e2e_evidence V4.5.14/V4.5.15 占位。详见 [V4.5.16_RELEASE_NOTES.md](release_notes/V4.5.16_RELEASE_NOTES.md) 与 `docs/release_notes/V4.5.16_RELEASE_NOTES.md`。

**V4.5.0 新增/增强模块**（合并 V4.4.3 + V4.4.4 + V4.5.0）:
- `scripts/collaboration/scratchpad_history_store.py` (ScratchpadHistoryStore — SQLite 跨会话 Scratchpad 搜索)
- `scripts/collaboration/agent_identity.py` (AgentIdentity — 确定性 agent ID 用于跨会话追踪)
- `scripts/collaboration/workflow_trace.py` (WorkflowTrace — dispatch 报告透明工作流追踪)
- `scripts/collaboration/git_context.py` (GitContext — Git 分支/commit 上下文注入 dispatch)
- `scripts/collaboration/skill_provider.py` (SkillProvider Protocol — 协议原生 Skill 架构，Builtin + MCP providers)
- `scripts/collaboration/output_style.py` (OutputStyle — 行动优先报告格式，源自 i-have-adhd 洞察)
- `scripts/cli.py` SessionResume (CLI `devsquad sessions list` + `dispatch --resume` 跨会话恢复)
- `scripts/collaboration/file_bundler.py` (FileBundler — review 模式确定性文件打包，源自 open-code-review)
- `SKILL.md` 模块化拆分 (1216→282 行 + 3 参考文档: MODULE_REFERENCE.md / SUB_SKILLS.md / VERSION_HISTORY.md)
- `docs/VISION.md` + `docs/VISION_ORCHESTRATION.md` + `docs/VISION_AGENT_COLLABORATION.md` (VISION 文档)

**V4.4.2 新增/增强模块**:
- `scripts/collaboration/models_dispatch.py` (P1-1 多语言角色 prompt — `RoleDefinition` 增加 `prompt_i18n`/`name_i18n` 字段 + `get_localized_prompt(lang)`/`get_localized_name(lang)` 方法 + 7 角色补全 EN/JP 翻译 + `_call_counter` 防幽灵)
- `scripts/collaboration/dispatch_pre_steps.py` (P1-1 调度链路接入 `get_localized_prompt(lang)` 替代直接访问 `prompt` 字段)
- `scripts/dashboard/dispatch_views.py` (P1-2 Dashboard 6-Tab 可见性增强 — `render_dispatch_result` 从 2 Tab 扩展为 6 Tab: Worker Outputs / Consensus / Risk Management / Retrospective / Full Report / Raw Data + 空状态处理)

**V4.4.1 新增/增强模块**:
- 外部文档重构（archive orphan i18n docs, retire CHANGELOG-CN, consolidate admin credentials, renumber INSTALL methods, sync version numbers across all external docs）
- 6 条测试教训整合到 Tester role + 测试流程（V4.4.1 M2b: 6 testing lessons into tester role and test flow）
- 真实用户模拟 E2E 测试 17 tests + NPS 报告（V4.4.1 M2: real user simulation E2E testing）

**V4.4.0 新增模块**:
- `scripts/collaboration/risk_register.py` (P0-1 PMP 风险管理 + 7 角色加权评估 + 4 种响应策略)
- `scripts/collaboration/viewpoint_registry.py` (P0-2 TOGAF 视点框架 + 7 角色绑定 + 正交性判断)
- `scripts/collaboration/error_budget_tracker.py` (P1-1 SRE 错误预算 + P10 部署门禁)
- `scripts/collaboration/gap_analyzer.py` (P1-2 TOGAF 差距分析 + LoopScheduler 决策驱动)
- `scripts/collaboration/dora_metrics_collector.py` (P2-1 DORA 4 指标 + P11 门禁)

**V4.3.2 新增模块**:
- `scripts/collaboration/quality_calibration_gate.py` (Gate 0 仪器校准门)
- `scripts/collaboration/role_specific_mock_backend.py` (角色特定 Mock 后端)
- `scripts/collaboration/quality_probe_slice.py` (Slice 1 薄切片探针)
- `scripts/generate_quality_decision_report.py` (CLI 报告生成器)

**V4.3.0 新增模块**:
- `scripts/collaboration/todo_drift_monitor.py` (P0-2 技术债持续监控)
- `scripts/collaboration/ponytail_debt_collector.py` (P1-1 Ponytail 债务收集)
- `scripts/collaboration/requirement_tracer.py` (P1-1 需求追踪)
- `scripts/collaboration/loop_engineering/rollback_strategy.py` (P1-4 Loop 回退策略)
- `scripts/qa/uiux_subitems.py` (P1-5 UIUX 子项审计)
- `scripts/dashboard/v43_panels.py` (P1-6 Dashboard V4.3.0 面板)

**关键模块分类**:
- **调度核心**: MultiAgentDispatcher, Coordinator, Worker, ConsensusEngine
- **上下文管理**: ContextCompressor, DualLayerContextManager, Scratchpad
- **安全**: PermissionGuard, InputValidator, AuthManager, OperationClassifier
- **性能**: PerformanceMonitor, WarmupManager, LLMCache, LLMRetry
- **生命周期**: LifecycleProtocol, UnifiedGateEngine, WorkflowEngine
- **集成**: API Server (FastAPI), Streamlit Dashboard, HistoryManager
- **控制论增强**: FeedbackControlLoop, ExecutionGuard, AdaptiveRoleSelector
- **V4.3.0 新增**: TodoDriftMonitor, PonytailDebtCollector, RequirementTracer, RollbackStrategy, UIUXSubitems, V43DashboardPanels

---

## 3. 测试统计

以下是本轮本地可复现结果。它们不替代 GitHub Actions 的权威结果。

| 检查 | 结果 | 状态 |
|----------|------|------|
| 测试质量门 | 扫描 403 个测试文件；0 MAJOR；785 MINOR | ✅ 通过（MINOR 仅告警） |
| 测试质量门回归 | 280 passed（含 4 个标记迁移文件 + MCP/REST/金字塔/基线门） | ✅ 通过 |
| 测试金字塔回归 | 53 passed | ✅ 通过 |
| 性能基线门回归 | 34 passed（含默认版本 v4.7.0 断言修复） | ✅ 通过 |
| 测试金字塔结构 | 9873 tests / 403 files；unclassified 0 | ✅ 结构通过（2026-10-22 dogfooding 报告采集） |
| 测试金字塔比例 | unit 73.7%，integration 14.9%，e2e 5.0%，contract 5.3%，security 0.6% | ⚠️ integration 低于 15% 目标 |
| 主测试全量回归 | 8312 passed, 17 skipped；覆盖率 79.48%（≥70% 门） | ✅ 通过（2 failed 已处置：1 个断言修复 + 1 个外部波动重试通过） |
| Ruff lint + format | All checks passed；1104 files formatted（2026-10-22 本地实测） | ✅ 通过 |
| mypy（scripts/ + skills/） | 0 errors | ✅ 通过 |
| 版本一致性 | 82/82（2026-10-22 本地实测；V4.8.0 bump 后全绿；4 层 TRAE cache 已同步） | ✅ 通过 |
| 配置一致性 | 7/7 | ✅ 通过 |
| Bandit | 0 HIGH / 0 MEDIUM / 100 LOW（docs/audits/bandit_v4.7.0.json） | ✅ 通过 |
| pip-audit | runtime requirements.lock 严格审计无已知漏洞；dev 面（site-packages + requirements-dev.lock）对 Pillow 包级时限性豁免（TD-075：12.3.0 累计 24 项 CVE 且持续披露，唯一修复版 13.0.0 与 streamlit≤1.66.0 不可共存；2026-10-22 起豁免清单运行时自动收集） | ✅ 通过（豁免已披露） |
| dispatcher size gate / skill contract / module activation / hidden content / dependency lock+sync | 全部 PASS | ✅ 通过 |
| 性能基准（CI performance job 同款命令） | 23 passed | ✅ 通过 |
| 性能基线文件 | 已刷新为 V4.7.0：mock 路径真实测量（50 样本 + 5 warmup 丢弃，p95≈0.0015ms）；host/api/auto_fallback 仍为 stub（snapshot_id 带 `_stub` 标记，发布 tag 时需真实环境替换） | ✅ mock 已测量；⚠️ host/api 为 stub |
| E2E + integration 全量 | 1670 passed, 4 skipped（1 failed 为 `test_llm_replay_subprocess` 偶发超时，单独重跑 211s 通过，非产品回归） | ✅ 通过 |
| Dashboard 用户旅程（含 slow 标记，CI `-m "not slow"` 不覆盖） | 96 passed, 1 skipped（12 个浏览器级旅程：登录/导航/RBAC/Task Dispatch/确定性渲染） | ✅ 通过 |
| 权威 CI（PR #59，V4.8.0 bump） | CI 主矩阵 + Perf Baseline + No Secrets + e2e + lint + security + deployment 运行中/全绿后合并（首跑 3.12 腿 1 failed：gate 结构测试锚定 devsquad-version 默认值，随发布有意识 bump 同步更新锚点后重跑） | ⏳ 合并后以 CI 实测更新本行 |

**测试质量说明**: 质量门不再把嵌套测试目录遗漏。测试中的 `assertTrue` 等 MINOR 项仍需持续治理，但当前不构成 MAJOR 阻断。

**测试金字塔说明**: `tests/security/` 已纳入独立 security 层。未分类测试为 0。集成测试比例为 14.9%，没有通过降低目标或隐藏警告来制造绿灯。

---

## 4. 硬约束验证

| 硬约束 | 状态 |
|--------|------|
| HC-1 rbac_fail_closed=True | ✅ PASS |
| HC-2 ConsensusGate 前置介入 | ✅ PASS |
| HC-3 禁止 fail-open | ✅ PASS |
| 三贤者并行投票 | ✅ PASS |
| 版本号一致性 | ✅ 已修复 (15/15) |
| 不在 localStorage 明文存敏感信息 | ✅ PASS |
| 专业版路由 API Key 验证 | ✅ PASS |
| 一键启动脚本 start.sh | ✅ PASS |
| 依赖锁文件 | ✅ PASS |
| CI mypy 阻塞 | ✅ PASS |
| E2E 模拟真实用户测试 | ✅ PASS |
| release.yml 含 publish-pypi job | ✅ PASS (API token + version consistency) |
| git tag 作为发布触发器 | ✅ PASS (v3.9.2) |

---

## 5. P0 修复成果（Round 9, 2026-07-01）

| P0 | 修复内容 | 测试数 |
|----|----------|--------|
| P0-1 | 密码哈希 SHA-256 → PBKDF2-HMAC-SHA256 + salt + 迁移 | 31 |
| P0-2 | scripts/start.sh 一键启动脚本（4 阶段） | 14 |
| P0-3 | requirements.lock 依赖锁文件 | 6 |
| P0-4 | VERSION 文件恢复 + 版本一致性 15/15 | 7 |
| P0-5 | E2E/集成测试从 norecursedirs 移除，改为 marker 过滤 | — |
| P0-6 | 测试覆盖率 25.26% → 68.15%，新增 trio 测试文件 | 31 |

---

## 6. P1-P2 修复成果（2026-06-29）

| 修复项 | 内容 |
|--------|------|
| P1-1 | CHANGELOG + README×3 + SKILL.md 同步 P0 修复记录 |
| P1-2 | 创建 docs/PROJECT_STATUS.md（本文件） |
| P2-1 | 清理 5 个嵌套空目录 + 修复 checkpoint_manager.py mkdir 根因 |
| P2-2 | flake8 清理新测试文件（30→0 违规） |
| P2-3 | CI mypy 扩展覆盖 scripts/ 全量（✅ 已升级为 0-error 阻断门禁，原 baseline=115） |
| P2-5 | README.md 语言混杂修复（中文标题→英文） |

---

## 7. 已知技术债

| 编号 | 描述 | 目标版本 | 状态 |
|------|------|----------|------|
| TD-067 | mypy 112 errors（scripts/ 全量） | V3.10.0 (<50) | ✅ 历史债务已清零 |
| TD-068 | 24 个 Mixin 类爆炸风险 | — | ✅ 评估后关闭；当前属于职责拆分，不是已证实缺陷 |
| TD-069 | bandit 中低危告警 | — | ✅ 本轮已重新执行：0 HIGH / 0 MEDIUM / 100 LOW（docs/audits/bandit_v4.7.0.json）；权威 CI 复验完成（PR #37/#38 全绿） |
| TD-070 | PromptAssembler + WorkflowEngine 测试缺口 | — | ✅ 幽灵债务关闭：AST 与文本检索证实两个类在源码与测试中均不存在，债务对象已消失 |
| TD-071 | 性能基线曾为 V4.5.2 历史 stub 数据 | V4.7.0 | ✅ 大部分关闭（2026-10-20 P0-W3）：mock + **api 真实测量**（openai backend，180s budget 内，snapshot_id 无 `_stub`，门禁 34 测试绿）；host 诚实保留 stub（environment_blocked：需 TRAE IDE 会话环境）；auto_fallback 按设计 stub |
| TD-072 | 集成测试比例 14.9%，低于 15% 目标 | V4.7.0 | ✅ 本轮已关闭：新增 13 个围绕 TD-002 的 integration 测试，金字塔 healthy（15.0%，1472/9808） |
| TD-073 | CI 性能检查和金字塔命令曾使用非阻塞写法 | V4.7.0 | ✅ 本轮已移除相关 `|| true`；本地验证通过；权威 CI 复验完成（PR #37/#38 全绿） |
| TD-074 | 文档仍有历史版本和旧能力数字 | V4.7.0 | ✅ 本轮已关闭：修正 19 处现在时态未验证断言（README×3/INSTALL/CLAUDE）；历史记录按原则保留 |
| TD-075 | Pillow 12.3.0 CVE 生态阻塞（dev 依赖审计面） | — | ⚠️ OPEN（2026-10-21 登记）：唯一修复版 13.0.0 与 streamlit≤1.66.0 不可共存；时限性豁免 2026-10-22 起运行时自动收集（site-packages 先卸载 + dev-lock 两遍审计自动生成清单），有披露有复查条件，详见 [TECH_DEBT.md](TECH_DEBT.md) |
| TD-076 | MCP server 与 mcp SDK 2.x 不兼容（依赖约束过宽） | V4.8.0 | ✅ RESOLVED（2026-10-22，PR #55）：pyproject extras `mcp`/`all` 收紧为 `mcp>=1,<2`；干净 venv 实测 mcp 1.30.0 MCP stdio 全链路可用（R4 e2e 证据）。PyPI 4.7.x 用户过渡期按 MCP.md `"mcp<2"` pin |

> 注：本表曾将"Ruff noqa 迁移（25 处，V4.7.0 批次）"与"host exit 2 修复（V4.7.0 批次）"误标为 TD-075/076；2026-10-22 按 [TECH_DEBT.md](TECH_DEBT.md) 权威台账对齐（TD-002=host exit 2 已 RESOLVED；TD-075=Pillow、TD-076=mcp 如上）。Ruff noqa 迁移为真实修复记录，保留于本注。

---

## 8. 代码质量基线

| 指标 | 当前值 | 目标 |
|------|--------|------|
| ruff | All checks passed（lint + format，1088 files） | 0 |
| mypy (scripts/collaboration/) | 0 errors | 0 |
| mypy (scripts/ + skills/ 全量) | 0 errors (阻断门禁，原 112) | 0 ✅ |
| bandit | 0 HIGH / 0 MEDIUM / 100 LOW（本轮重扫） | 0 HIGH/MEDIUM ✅ |
| pip-audit | runtime lock 严格审计无已知漏洞；dev 面 Pillow 包级时限性豁免（TD-075，累计 24 项 CVE 且持续披露） | 0 ✅ |
| flake8 (新测试文件) | 0 | 0 |
| 版本一致性 | 80/80（含 4 层 TRAE cache 内容一致） | 80/80 |
| pre-commit hooks | 已配置 (ruff + mypy + 版本一致性) | 已配置 |

---

## 9. 下一步计划

1. **完成 V4.7.0 发布前验证**
   - ✅ 执行全量 unit/contract/security 回归（8312 passed，覆盖率 79.48%）。
   - ✅ 执行 E2E + integration 全量（1670 passed；1 个偶发超时单独重跑通过）。
   - ✅ 执行 Mypy、Bandit、pip-audit、版本一致性和配置一致性检查（全部通过）。
   - ✅ 执行性能基准（23 passed）。
   - ✅ Dashboard 真实用户旅程 UI 级验证：96 passed, 1 skipped（12 个浏览器级旅程含登录/导航/RBAC/Task Dispatch/确定性渲染；skip 为 auth disabled 模式下登录表单测试的设计内跳过）。注意：这批测试带 `slow` 标记，被 CI e2e job 的 `-m "not slow"` 排除，发布前必须本地补跑。
   - 在可用环境执行 Docker、Helm、Prometheus 工具检查；不可用时记录为 environment_blocked。
2. **刷新性能基线**
   - ✅ mock 路径已用真实 MockBackend.generate 调用重新采集（50 样本 + 5 warmup 丢弃）。
   - ⚠️ host/api/auto_fallback 仍为 stub；在具备真实环境的发布 tag 前替换为真实测量。
3. **处理质量结构债务**
   - 增加有真实价值的集成测试，使比例达到 15% 目标。
   - 持续减少 785 个 MINOR 测试质量告警，不用批量豁免隐藏问题。
4. **发布治理**
   - 提交本轮变更到功能分支，创建或更新 Pull Request。
   - 等待权威 CI 全绿后，由仓库所有者按单维护者流程合并。
   - 在所有阻塞项关闭前，不创建 `v4.7.0` tag，不创建 GitHub Release。

---

## 10. 评估历史

| 轮次 | 日期 | 综合评分 | 硬约束 | 关键改进 |
|------|------|----------|--------|----------|
| 第一轮 | 2026-06-26 | 7.3 | - | 基线建立 |
| 第二轮 | 2026-06-27 | 7.1 | - | 7 维度细化 |
| 第三轮 | 2026-06-28 | 8.0 | 9/11 | 文档同步 + fail-closed + 幽灵函数清理 |
| 第四轮 | 2026-06-28 | 8.3 | 11/11 | P0 修复（密码哈希 + start.sh + 锁文件） |
| 第五轮 | 2026-06-29 | 8.5 | 11/11 | P1-P2 修复（文档同步 + 空目录 + flake8 + CI mypy） + E2E 测试 5/5 全通过 |
| 第六轮 | 2026-06-29 | 8.9 | 11/11 | P0 RBAC fail-open 修复 + P1 死代码 + CI timeout + 文档三语对齐 |
| 第七轮 | 2026-06-30 | 9.1 | 13/13 | cookie 安全 + release.yml + .pre-commit + git tag + CI 僵尸配置清理 |
| 第八轮 | 2026-06-30 | 9.3 | 13/13 | mypy 112→0 + bandit 11→0 + TD-068 降级关闭 + CI mypy 阻断门禁 |
| **V3.10.0 Round 1** | **2026-07-02** | **8.1** | **13/13** | **Phase 1+2 完整交付、无幽灵功能、CI 全绿、基准可量化** |
| **V3.10.0 Round 2** | **2026-07-02** | **8.3** | **13/13** | **UI 启动验证、多语言一致性、CI mypy 扩展、artifact fallback、幽灵功能深度审计** |
| **V4.0.0 发布前审查** | **2026-07-07** | **8.4** | **13/13** | **6 特性全部交付、文档一致性修复、上游对比 84.3%、待补 E2E 测试** |
| **V4.0.0 项目整理评估** | **2026-07-10** | **8.6** | **13/13** | **3666 tests 全绿、.gitignore 大小写 bug 修复、文档测试数同步、SKILL.md 测试表补全 V4.0.0 行、无幽灵功能验证** |
| **V4.0.0 P0-P2 改进** | **2026-07-10** | **8.7** | **13/13** | **mypy/ruff 版本锁定、streamlit/Pillow 加入 [dev] extras、e2e 在 PR 时运行、God Class 检测改为职责检测(23→4 候选)、broad-except 收窄** |
| **V4.0.10 项目整理评估** | **2026-07-13** | **8.8** | **13/13** | **4651 tests 全绿、redis_url 凭据泄露防护 + health_check bug 修复、依赖同步(requirements-dev.txt/[all] extras)、CI 3.12 矩阵、pre-commit ruff 版本对齐、5 文件版本引用刷新、文档测试数同步** |
| **V4.0.11 文档审核** | **2026-07-14** | **8.9** | **13/13** | **全面文档审核(57 issues: 16 P0+23 P1+18 P2)、health_check 版本硬编码 3.9.2→DEVSQUAD_VERSION 修复、CI 覆盖率门禁 --cov-fail-under=75 启用、模块数统一 185+(8 文件)、INDEX.md 路径修复、历史文档 superseded 标注** |
| **V4.1.3 UI/UX 整合发布** | **2026-07-20** | **9.0** | **13/13** | **UI/UX 4-Wave 提升全部完成（180 新测试零回归）、Phase 3 本地 TRAE 环境验证 148 检查点全通过、5355 tests 全绿、版本号 18 处全量同步、5 道 CI 质量门全绿、Morandi 配色 + 暗色模式 + SVG 图标 + 命令面板 + i18n + Skeleton + 键盘快捷键** |
| **V4.4.0 P0-P3 增强模块** | **2026-07-29** | **9.1** | **13/13** | **5 个新模块全部交付（RiskRegister / ViewpointRegistry / ErrorBudgetTracker / GapAnalyzer / DoraMetricsCollector）、13 E2E 从 xfail 转 xpass、8155 tests 全绿、防幽灵 `_call_counter > 0` 验证通过、ruff/mypy/radon 全绿** |
| **V4.4.1 文档重构 + 用户测试** | **2026-07-30** | **9.2** | **13/13** | **外部文档重构（archive orphan i18n + retire CHANGELOG-CN + consolidate admin credentials + renumber INSTALL）、17 真实用户模拟 E2E 测试通过（NPS 报告）、6 条测试教训整合到 Tester role** |
| **V4.4.2 P0-P3 增强** | **2026-07-30** | **9.2** | **13/13** | **P1-1 多语言角色 prompt EN/CN/JP + P1-2 Dashboard 6-Tab 可见性增强 + P2/P3 评估报告（缓办至 V4.6.0/V5.0.0+）、22 新测试通过（含副作用验证 call_counter + localized prompt 实际下发）、测试全绿、文档同步 ARCHITECTURE_V4/PROJECT_STATUS/3 README** |
| **V4.5.0 跨会话 + Skill 协议** | **2026-08-03** | **9.3** | **13/13** | **10 项新特性（ScratchpadHistoryStore + AgentIdentity + WorkflowTrace + GitContext + SkillProvider Protocol + OutputStyle + SessionResume CLI + FileBundler + SKILL.md 模块化拆分 1216→282 + VISION 文档）、8 原子子 Skill（新增 prototype + teach）、测试全绿、防幽灵 `_call_counter > 0` 验证通过、3 语言 README 同步** |
| **V4.5.1 Approval Gate + Connector** | **2026-08-05** | **9.3** | **13/13** | **2 新模块（ApprovalGate fail-closed 用户级审批门 + ConnectorFramework GitHub 连接器 api/cli/simulation 三模式）、3 ROADMAP 项完成（V451-7 Dashboard AppTest 11 用例 + V451-8 REST API 190 E2E + V451-9 Connector 反幽灵 12 E2E）、DispatchResult +4 字段向后兼容、测试全绿、防幽灵 `_call_counter > 0` 验证通过、187+ 模块** |

评估报告路径:
- V3.9.2: `docs/_archive/assessments/PROJECT_TIDY_ASSESSMENT_V3.9.2_round*.md`
- V3.10.0-dev Round 1: `docs/_archive/assessments/PROJECT_TIDY_ASSESSMENT_V3.10.0_round1.md`
- V3.10.0-dev Round 2: `docs/_archive/assessments/PROJECT_TIDY_ASSESSMENT_V3.10.0_round2.md`
