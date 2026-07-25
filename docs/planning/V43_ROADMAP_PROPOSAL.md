# DevSquad V4.3 统一推进方案 (Roadmap Proposal v1.2)

> **文档类型**: V4.3 战略规划提案 — 用户确认后修订版
> **创建日期**: 2026-07-24
> **修订日期**: 2026-07-24 (v1.2 — P2-1 并入 V4.3.0，版本策略改为 V4.2.9→V4.3.0)
> **基线版本**: V4.2.1 (commit 1fc94aa)
> **目标版本**: V4.2.9 (预发布，全部代码+文档完成) → V4.3.0 (用户确认后正式版)
> **维护者**: DevSquad Team
> **状态**: CONSENSUS_REACHED + USER_APPROVED — 7-Role 共识 + 用户确认，按项目生命周期推进

---

## 1. 背景与目标

### 1.1 整合三方面输入

本方案整合以下三方面输入，制定 V4.3 统一推进路线：

| # | 输入来源 | 现状基线 | 关键发现 |
|---|----------|----------|----------|
| 1 | **技术债跟踪** ([TECH_DEBT.md](../TECH_DEBT.md)) | 1 项 P3 信息性条目，无真实可执行 TODO | 基线干净，但缺少"持续监控 + 入门文档"机制 |
| 2 | **pickle→JSON 迁移** (`cache_interface.py`) | 4 处 pickle 使用（2 处 dead code + 1 处 fallback + 1 处文档残留） | 可分两阶段安全迁移，无复杂对象依赖；fallback 被 Redis 调用需安全收紧 |
| 3 | **上游 TraeMultiAgentSkill v2.6-v2.8 启发** | DevSquad 已有 Ponytail/Autonomous/Loop/UIUX/PluginHotLoader 基础实现 | 6 个精细化点中 2 项已对齐、3 项可借鉴升级、1 项违反 YAGNI 降级 |

### 1.2 V4.3 核心目标

1. **消除安全债**: pickle→JSON 迁移完成，移除 `pickle.loads` 反序列化风险面；fallback 安全收紧
2. **精细化升级**: 借鉴上游 v2.6-v2.8 的 4 个可借鉴点（Ponytail/Loop/UIUX/Dashboard 可视化），将 V4.0.0 基础实现升级为生产级
3. **技术债持续治理**: 建立"扫描-登记-修复-验证"闭环流程，避免技术债再次积累
4. **保持 SemVer 合规**: MINOR 版本递增（V4.2.1 → V4.3.0），所有变更为向后兼容的功能新增

### 1.3 不做的事 (Non-Goals)

- 不重写 V4.0.0 已有的 Loop/Autonomous/UIUX/PluginHotLoader 基础架构
- 不破坏现有 7400+ CI 测试（必须 100% 向后兼容）
- 不修改 V4.2.1 已落地的 P2-1/P2-2/P2-4/P2-UI-1/2/3 公共 API
- 不新增 Dynamic Workflows 6 模式库（降级为 P3-1，待真实需求出现再建）
- 不修改现有 `LoopEngineeringConfig.max_iterations`（默认 50，保持不变）

---

## 2. 三方面基线现状

### 2.1 技术债基线

**扫描命令**: `grep -rn "TODO\|FIXME\|HACK" scripts/ --include="*.py" | grep -v "test\|__pycache__"`

**结果**:
- 18 行匹配 → 17 行为技术债检测工具自身实现代码（regex/enum/docstring）
- 1 行为描述性注释（`tech_debt_manager.py:477` 段落标题）
- **真实可执行 TODO 数: 0**

**结论**: DevSquad 在 V4.0.11 时已清理至 0，V4.2.1 仍保持 0 基线，技术债健康度良好。

**Gap**: 缺少"持续监控 + 入门文档"机制，新引入的 TODO 不会被自动登记到 TECH_DEBT.md。

### 2.2 pickle→JSON 迁移基线

**扫描结果**（共 26 行匹配，集中在 2 个文件）:

| 位置 | 类型 | 状态 | 迁移策略 |
|------|------|------|----------|
| `cache_interface.py:168-170` | 运行时 fallback（legacy 反序列化） | 活跃（被 Redis 调用） | P0-1 安全收紧 + P2-1 移除（7-14 天观察期） |
| `cache_interface.py:207-215` | dead code (`format="pickle"` 序列化分支) | 废弃 | P0-1 直接删除 |
| `cache_interface.py:246-256` | dead code (`format="pickle"` 反序列化分支) | 废弃 | P0-1 直接删除 |
| `cache_interface.py` 文档残留 | docstring/comment | 文档 | P0-1 同步清理 |
| `redis_cache.py:119` | 接口参数 (`serialization_format: 'json'/'pickle'`) | 接口保留 | 保留 'json' 选项，移除 'pickle' 选项说明 |

**迁移可行性确认**:
- DevSquad 缓存数据全部为 JSON 可序列化类型（dict/list/str/int/float/bool/None）
- 无自定义 Python 对象依赖 pickle
- `pickle.loads` 是 OWASP A08:2021 注入风险面
- **Security 关切**: fallback 被 `redis_cache.py:289/419` 调用，Redis 是网络服务，nosec "trusted local" 假设不成立

### 2.3 上游 TraeMultiAgentSkill v2.6-v2.8 启发（修订后）

**对比分析**: DevSquad V4.0.0 已实现上游 v2.6-v2.8 的大部分基础能力，7-Role 评估修正了 gap 分析。

| 上游特性 | DevSquad 现状 | 精细化 Gap（修订后） | V4.3 借鉴方案 |
|----------|--------------|-----------|---------------|
| **v2.6 Ponytail 决策梯** | V3.10.0 已有 7 步梯 + 静态注入 | 缺 lite/full 双模式 / 16 条红线 / DebtCollector / RequirementTracer | P1-1: 升级 PonytailRuleInjector（保留 7 步梯，删 ultra） |
| **v2.6 Autonomous 智能确认** | V4.0.0 P3-1 已有 SmartConfirmation 三态 | **已对齐**，仅需补充风险评分文档 | P2-2: 文档补全（不新增代码） |
| **v2.6 Dynamic Workflows 6 模式** | 无 | 完整缺失，但**无真实消费者，违反 YAGNI** | **P3-1: 降级**（待真实需求出现再建） |
| **v2.6 插件热加载 3 路径** | V4.0.0 P3-2 已有 3 路径 + `reload_if_changed()` + `no_hot_reload` + `poll_interval_sec` + `scan_drop_in_dir()` | **已对齐**（原 gap 分析错误） | **P3-2: 降级为文档项**（能力对齐说明） |
| **v2.7 UI/UX 巡检 4 维度** | V4.0.0 P1-2 UIUXAnalyzer 4 维度 + V4.1.0 扩展（6 anti-pattern / OKLCH / 4pt grid）+ V4.1.1 DeterministicRuleEngine 46 规则 | DevSquad **已超过**上游 v2.7 | P1-5: 子项审计 + 按需补全（升级自 P2-3） |
| **v2.8/v2.8.1 八阶段 Loop + 精准回退** | V4.0.0 P1-1 LoopKernel 五步闭环 | 缺 RollbackStrategy 精准回退 + 累计上下文传递 | P1-4: 升级 LoopKernel 回退策略（独立硬上限） |

---

## 3. V4.3 推进方案 (按优先级分阶段 — 修订后)

### 3.1 P0 阶段 — 安全债清理（必做）

#### P0-1: pickle→JSON 迁移 阶段 1 — 删除 dead code + fallback 安全收紧

**目标**: 移除 `cache_interface.py` 中 2 处 dead code 分支 + 文档残留 + fallback 安全收紧

**变更范围**:
- `scripts/collaboration/cache_interface.py`
  - 删除 L207-215 `elif format == "pickle":` 序列化分支
  - 删除 L246-256 `elif format == "pickle":` 反序列化分支
  - 更新 docstring：移除 `'pickle' deprecated` 说明
  - **L168-170 fallback 安全收紧**（Security 共识调整 4）:
    - 强制 Redis URL 含密码，或 fallback 改为显式 opt-in 默认关闭
    - 添加注释说明 Redis 是网络服务，nosec "trusted local" 假设不成立
- `scripts/collaboration/redis_cache.py`
  - L119 docstring 移除 `'pickle'` 选项说明
- **一次性 Redis 缓存 pickle payload 扫描**（P0-1 完成后执行）

**测试**:
- 现有 `tests/test_cache_interface.py` 全部通过（无测试覆盖 dead code 分支）
- 新增 1 个测试：`test_serialize_rejects_pickle_format` 验证 `format="pickle"` 抛出 `ValueError`
- 新增 1 个 E2E 测试：`test_cache_pickle_migration_journey.py` 验证遗留 pickle 缓存加载/拒绝/迁移路径（Tester 共识调整）

**风险**: 低。dead code 无运行时调用方；fallback 收紧需验证不破坏现有 Redis 部署。

#### P0-2: 技术债持续监控机制（`todo_drift_monitor.py`）

**目标**: 建立"扫描-登记-修复-验证"闭环，避免技术债再次积累

**变更范围**:
- 新增 `scripts/collaboration/todo_drift_monitor.py`（轻量脚本，<100 行）— **改名**（Architect 共识调整 5）
  - `scan_tech_debt()` — 扫描 `scripts/` 目录 TODO/FIXME/HACK
  - `diff_with_tracker()` — 对比 TECH_DEBT.md 已登记条目
  - `report_new_debts()` — 输出新引入的技术债列表
  - **regex 大小写不敏感 + 扩展标记集**（Security 共识调整 5）: `TODO|FIXME|HACK|XXX|WIP|待办|待修复`
- 集成到 `.pre-commit-config.yaml` local hook — **改为阻塞**（DevOps 共识调整 5）
- 集成到 CI `lint` job（阻塞，新增 TODO 未登记则 fail）
- **PR template 增加"无未登记技术债"reviewer 复选框**（Security 共识调整 5）

**测试**:
- `tests/test_todo_drift_monitor.py`（约 15 测试）

**风险**: 低。脚本只读，不修改源码。

### 3.2 P1 阶段 — 上游精细化升级（重要）

#### P1-1: Ponytail 决策梯精细化升级（简化版）

**目标**: 将 V3.10.0 静态注入升级为双模式可配置精细化模式

**变更范围**（Coder+Tester 共识调整 3 — 删除 ultra，保留 7 步梯）:
- `scripts/collaboration/ponytail_rule_injector.py` 升级
  - **保留 7 步梯**（不重命名为 6 步梯，避免破坏 `test_contains_all_7_rungs` 断言）
  - **保留 `PONYTAIL_RULES` 原文本**作为 `full` 模式默认输出（向后兼容 17 现有测试）
  - **新增 `PONYTAIL_RULES_LITE` 常量**供 `lite` 模式（测试/UI 角色）
  - **删除 `ultra` 模式**（自动降级即死代码，违反 Ponytail 红线"Deletion over addition"）
  - 新增 16 条不可简化红线: 6 条原始 Ponytail 红线 + 10 条项目规则红线
- 新增 `scripts/collaboration/ponytail_debt_collector.py`
  - 扫描 `# ponytail:` 注释标记
  - 区分"有升级路径"与"腐烂风险"债务
- 新增 `scripts/collaboration/requirement_tracer.py`
  - 解析 `[REQ-XXX]` 标记
  - 中文关键词提取 + 实现检测

**配置**: `.devsquad.yaml` 新增 `quality_control.ponytail_mode: lite|full`（仅 2 模式）

**测试**:
- `tests/test_ponytail_rule_injector.py` 现有 17 测试 — **需同步修改 1 个**（`test_contains_all_7_rungs` 参数化，支持 lite/full 双模式断言）
- 新增约 25 测试覆盖模式切换 / 红线检测 / 债务收集 / 需求追踪

**风险**: 中。需保持 `full` 模式向后兼容（与 V3.10.0 行为一致）。

#### P1-4: LoopKernel 精准回退策略

**目标**: 借鉴上游 v2.8.1 WorkflowLoopController + RollbackStrategy，补全 V4.0.0 P1-1 LoopKernel 的回退能力

**变更范围**（Architect 共识调整 10 — 独立硬上限）:
- `scripts/collaboration/loop_engineering/kernel.py` 升级
  - 新增 `RollbackStrategy` 类
    - `determine_rollback_stage(failure_stage)` — 失败阶段 → 回退目标阶段映射
    - D1/D2/D4/D5/D6 失败 → 回退到 DEVELOPMENT
    - D3 失败 → 回退到 TEST_VERIFICATION
  - 新增 `_accumulated_artifacts` 跨迭代传递
  - **新增独立 `rollback_max_iterations` 硬上限**（默认 3，可配置）— **不修改现有 `LoopEngineeringConfig.max_iterations`（默认 50）**
- 新增 `scripts/collaboration/loop_engineering/rollback_strategy.py`

**测试**:
- 现有 `tests/test_loop_engineering.py` 35 测试 — **需同步修改**（LoopScheduler ROLLBACK 维度测试）
- 新增约 12 测试覆盖回退映射 / 累计上下文 / 独立迭代上限

**风险**: 中。回退策略需严格验证不破坏现有 LoopKernel 五步闭环。

#### P1-5: UIUXAnalyzer 子项审计 + 按需补全（升级自 P2-3）

**目标**: 对比上游 v2.7 UI/UX 巡检 4 维度子项，补全 DevSquad 缺失项

**变更范围**（UI Designer 共识调整 6 — 升级为 P1）:
- 新增 `docs/audits/V43_UIUX_SUBITEM_COMPARISON.md`（活文档）
- 对比 4 维度（A11y / 交互 / 布局 / UX 反模式）的所有子项
- 标记 DevSquad 已有 / 缺失 / 差异项
- **按需补充缺失子项**（本阶段审计 + 补全，非仅审计）
- 基线: DevSquad UIUXAnalyzer 已超过上游 v2.7（V4.1.0 6 anti-pattern + OKLCH + 4pt grid + V4.1.1 DeterministicRuleEngine 46 规则）

**风险**: 低。基于现有 UIUXAnalyzer 增量补全。

#### P1-6: Dashboard 状态可视化（新增）

**目标**: 让 V4.3 后端能力对 Dashboard 用户可感知

**变更范围**（UI Designer 共识调整 7）:
- `scripts/collaboration/dashboard_live_mode.py` 升级
  - 暴露 Ponytail 模式指示器（lite/full）
  - 新增 Loop 回退状态面板（D1-D6 → 回退目标可视化）
  - 新增 Plugin 热加载事件流（复用现有 PluginHotLoader 审计日志）
- 为新增视图建立视觉回归 baseline（复用 `visual_regression.py` PIL Diff）

**测试**:
- `tests/test_dashboard_live_mode.py` 现有 28 测试保持通过
- 新增约 10 测试覆盖状态指示器 / 回退面板 / 事件流

**风险**: 低。Dashboard 增量 UI 扩展。

### 3.3 P2 阶段 — 收尾与文档（一般）

#### P2-1: pickle→JSON 迁移 阶段 2 — 移除 fallback

**前置条件**: P0-1 完成后，确认无遗留 pickle 缓存文件（运行 **7-14 天观察期**，Security 共识调整 4）

**变更范围**:
- `scripts/collaboration/cache_interface.py`
  - 删除 L168-170 pickle fallback 分支
  - 更新 docstring：移除"legacy pickle fallback"说明
- 更新 [TECH_DEBT.md](../TECH_DEBT.md) 登记 pickle 迁移完成

**测试**:
- 现有测试全部通过
- 新增 1 个测试：`test_deserialize_rejects_pickle_data` 验证非 JSON 数据抛出 `ValueError`

**风险**: 低。7-14 天观察期确保无遗留缓存。

#### P2-2: Autonomous SmartConfirmation 文档补全

**目标**: 将 V4.0.0 P3-1 SmartConfirmation 三态决策文档化

**变更范围**:
- 更新 [SKILL.md](../../.trae/skills/devsquad/SKILL.md) Autonomous 章节
- 新增 `docs/guides/AUTONOMOUS_MODE_GUIDE.md`
  - 三态决策说明（smart/whitelist-only/blacklist-only）
  - 风险评分算法说明
  - 黑白名单配置示例

**风险**: 无。纯文档变更。

#### P2-4: V4.3 发布文档同步

**目标**: 遵循"文档先行 + 文档同步"铁律

**变更范围**:
- 更新 [ROADMAP.md](../ROADMAP.md) 新增 V4.3+ Roadmap 章节
- 更新 [CHANGELOG.md](../../CHANGELOG.md) V4.3.0 条目
- 更新 [SKILL.md](../../.trae/skills/devsquad/SKILL.md) 版本号 / 模块数 / 测试数
- 更新 [README.md](../../README.md) 版本号 / 时间线
- 更新 [TECH_DEBT.md](../TECH_DEBT.md) 变更历史
- 运行 `python scripts/check_config_consistency.py` 验证一致性（DevOps 共识调整 8 — 修正脚本引用）

**风险**: 无。纯文档变更。

### 3.4 P3 阶段 — 待真实需求（暂不实施）

#### P3-1: Dynamic Workflows 6 模式库（降级自 P1-2）

**原因**（PM+Coder+Architect 共识调整 1）: 与 Non-Goals 矛盾；无真实消费者，违反 YAGNI；pattern_executor 易演变为 God Class。

**新定位**: 待真实需求出现再建。从 §1.3 Non-Goals 移除"不引入新核心模块"以消除矛盾。

#### P3-2: PluginHotLoader 轮询文档对齐（降级自 P1-3）

**原因**（Architect+DevOps 共识调整 2）: 现有 `plugins/hot_loader.py` 已实现 `reload_if_changed()`（mtime+checksum 双重检测）、`no_hot_reload` 开关、`poll_interval_sec` 参数、`scan_drop_in_dir()`。§2.3 第 4 行 gap 分析错误。

**新定位**: 在 SKILL.md 中明确标注现有能力（P2-4 文档同步时执行）。

---

## 4. 7-Role 共识评估矩阵

> 评估日期: 2026-07-24 | 7-Role 并行评估，全部 APPROVE_WITH_CONCERNS

| Role | 审查维度 | 意见 | 关键关切 | 建议调整 |
|------|----------|------|----------|----------|
| Architect | 架构一致性 / 模块边界 / 向后兼容 | APPROVE_WITH_CONCERNS | P1-3 为幽灵特性；`tech_debt_monitor` 命名冲突；7→6 步梯与 max_iterations 默认值兼容歧义 | P1-3 降级为 P3 文档项；tech_debt_monitor 改名 `todo_drift_monitor`；明确 `full` 模式保留 7 rungs + rollback 独立硬上限 |
| Security | 安全债清理 / 攻击面收敛 / 风险评估 | APPROVE_WITH_CONCERNS | pickle fallback 被 Redis 调用，"trusted local" 假设不成立，RCE 攻击面开放 30 天；regex 易绕过；Dynamic Workflows 防护缺失 | P0-1 同步收紧 fallback；P2-1 观察期缩至 7-14 天；regex 大小写不敏感 + 扩展标记集 |
| Tester | 测试策略 / 回归风险 / 覆盖率目标 | APPROVE_WITH_CONCERNS | `test_contains_all_7_rungs` 硬编码梯子关键词；新增 105 测试加剧金字塔失衡；E2E 缺 pickle 缓存兼容验证 | 测试需同步修改；新增 `test_cache_pickle_migration_journey.py` E2E；DynamicWorkflows 补 contract 测试 |
| PM | 优先级合理性 / 用户价值 / 范围控制 | APPROVE_WITH_CONCERNS | P1-2 与 Non-Goals 矛盾；范围过大；用户感知价值偏低 | 拆为 V4.3.0 + V4.4.0；Release Notes 突出可感知能力 |
| Coder | 实现复杂度 / 代码质量 / 可维护性 | APPROVE_WITH_CONCERNS | P1-2 过度设计；`ultra` 模式为死代码；复杂度阈值风险 | P1-2 降级为 P3 或删除；删除 `ultra` 模式；保留 PONYTAIL_RULES 原文本作为 `full` 默认 |
| DevOps | CI 集成 / 发布流程 / 监控告警 | APPROVE_WITH_CONCERNS | `check_doc_consistency.sh` 幽灵脚本；P1-3/P1-4 部分能力已存在；两阶段发布拖累文档 | 修正脚本引用；P2-2/P2-3/P2-4 并入 V4.3.0；V4.3.1 仅保留 P2-1；新增域监控指标 |
| UI Designer | UIUX 审计深度 / 用户感知 | APPROVE_WITH_CONCERNS | P2-3 应升级为 P1；V4.3 后端能力对 Dashboard 不可感知；未与 LiveBrowserMode 协同 | P2-3 升级为 P1-5；新增 P1-6 Dashboard 状态可视化 |

### 4.1 共识结论

**整体共识**: 7/7 APPROVE_WITH_CONCERNS — 方案方向正确，按 §4.2 调整清单修订后达成共识。

### 4.2 共识调整清单（10 项，已在 v1.1 中全部落地）

| # | 调整 | 共识角色 | v1.1 落地位置 |
|---|------|----------|---------------|
| 1 | P1-2 Dynamic Workflows 降级为 P3 | PM+Coder+Architect | §3.4 P3-1 |
| 2 | P1-3 PluginHotLoader 轮询降级为 P3 文档项 | Architect+DevOps | §3.4 P3-2 |
| 3 | P1-1 Ponytail 简化（删 ultra，保留 7 步梯） | Coder+Tester | §3.2 P1-1 |
| 4 | P0-1 pickle 安全收紧 + 观察期 30→7-14 天 | Security | §3.1 P0-1 + §3.3 P2-1 |
| 5 | P0-2 改名 `todo_drift_monitor` + regex 扩展 + 阻塞 | Security+Architect+DevOps | §3.1 P0-2 |
| 6 | P2-3 UIUX 升级为 P1-5 | UI Designer | §3.2 P1-5 |
| 7 | 新增 P1-6 Dashboard 状态可视化 | UI Designer | §3.2 P1-6 |
| 8 | 修正 `check_doc_consistency.sh` → `check_config_consistency.py` | DevOps | §3.3 P2-4 |
| 9 | 发布策略调整：V4.3.0 含文档，V4.3.1 仅 P2-1 | DevOps+PM | §6.3 |
| 10 | LoopKernel 回退独立硬上限 `rollback_max_iterations` | Architect | §3.2 P1-4 |

### 4.3 共识达成

**结论**: 7-Role 全部 APPROVE_WITH_CONCERNS，v1.1 已按 §4.2 调整清单全部修订，达成共识，可推进落地到 [ROADMAP.md](../ROADMAP.md)。

---

## 5. 风险与缓解（修订后）

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| pickle 迁移破坏遗留缓存 | 低 | P0-1 仅删 dead code + 安全收紧；P2-1 有 7-14 天观察期 |
| pickle fallback 被 Redis RCE 攻击 | 中 | P0-1 强制 Redis 密码或 opt-in 默认关闭；一次性 payload 扫描 |
| Ponytail 模式切换破坏现有行为 | 低 | 保留 `full` 模式为默认（PONYTAIL_RULES 原文本），与 V3.10.0 行为一致 |
| LoopKernel 回退策略误判 | 中 | 独立 `rollback_max_iterations` 硬上限 3 次，超限自动 STOP_FAILURE |
| CI 测试数下降（pickle 测试移除） | 低 | 同步新增迁移验证测试，保持总数 ≥7400 |
| 文档同步遗漏 | 低 | `check_config_consistency.py` CI 门禁 |
| `test_contains_all_7_rungs` 断言破坏 | 低 | P1-1 同步参数化修改（已声明） |
| Dashboard 新增视图视觉回归 | 低 | P1-6 建立视觉回归 baseline |

---

## 6. 落地计划与校验方法（修订后）

### 6.1 落地顺序（依赖图 — 修正后）

```
P0-1 (pickle dead code + 安全收紧) ──┐
P0-2 (todo_drift_monitor) ──────────┤
P1-1 (Ponytail lite/full 双模式) ───┤
P1-4 (LoopKernel RollbackStrategy) ─┤
P1-5 (UIUX 子项审计+补全) ──────────┤
P1-6 (Dashboard 状态可视化) ────────┤
                                    ├──→ P2-4 (发布文档同步, V4.3.0)
                                    │
                                    └──→ P2-1 (pickle fallback 移除, 7-14 天后, V4.3.1)

P2-2 (Autonomous 文档) ─────────────┘  (并入 V4.3.0)
P3-1 (Dynamic Workflows) ────────── 待真实需求
P3-2 (PluginHotLoader 文档对齐) ──── 并入 P2-4
```

### 6.2 校验方法（修正后）

| 阶段 | 校验项 | 命令 / 工具 |
|------|--------|-------------|
| 每个 P0/P1 项 | 单元测试 100% 通过 | `pytest tests/test_<module>.py -v` |
| 每个 P0/P1 项 | mypy 0 errors | `mypy scripts/collaboration/<module>.py` |
| 每个 P0/P1 项 | ruff 0 errors | `ruff check scripts/collaboration/<module>.py` |
| 每个 P0/P1 项 | radon cc < D | `radon cc scripts/collaboration/<module>.py -nd -s` |
| 全量回归 | 7400+ CI 测试通过 | `pytest tests/ -v` |
| 文档一致性 | 版本号同步 | `python scripts/check_config_consistency.py` |
| 安全扫描 | pickle 残留检测 | `grep -rn "pickle" scripts/ --include="*.py"` |
| E2E 用户旅程 | 真实场景验证 | `pytest tests/e2e/ -v` |
| pickle 迁移 E2E | 缓存兼容验证 | `pytest tests/test_cache_pickle_migration_journey.py -v` |
| Dashboard 视觉回归 | 新视图 baseline | `pytest tests/test_visual_regression.py -v` |

### 6.3 版本号策略（v1.2 修订 — 用户确认）

- **V4.2.9** (PATCH 预发布): 全部 P0 + P1 + P2 代码 + 文档同步完成，通过 E2E + 真实用户模拟测试，等待用户确认
- **V4.3.0** (MINOR 正式版): 用户确认 V4.2.9 后，升 MINOR 号发布
- **P2-1 已并入 V4.3.0**（不再单独 V4.3.1）— 用户指示合并推进
- 遵循 [project_memory SemVer 规则]: MINOR 递增仅用于向后兼容的功能新增
- **文档先行原则**: PRD / 架构设计 / 测试方案 / README 在代码实施前完成
- **项目生命周期**: 按 11-Phase 模型推进（P1 需求 → P2 架构 → P3 技术设计 → P7 测试计划 → P8 实施 → P9 测试执行 → P10 部署发布）
- **测试金字塔保障**: unit ≥60% / integration 15-25% / e2e ≤10% / contract 5-10% / smoke ≤5%
- **发布前必做**: E2E 测试 + 真实用户模拟测试（用户规则 3）

---

## 7. 变更历史

| 日期 | 版本 | 变更 | 负责人 |
|------|------|------|--------|
| 2026-07-24 | v1.0 | 初始提案；整合技术债 + pickle 迁移 + 上游 v2.6-v2.8 启发 | DevSquad |
| 2026-07-24 | v1.1 | 7-Role 共识评估后修订；按 10 项调整全部落地 | DevSquad |

---

> **文档结束**
>
> **状态**: CONSENSUS_REACHED — 已落地到 [ROADMAP.md](../ROADMAP.md) V4.3+ Roadmap 章节
