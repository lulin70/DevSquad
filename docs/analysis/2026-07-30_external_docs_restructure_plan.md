# DevSquad 外部文档多语言重构计划

> 审核日期: 2026-07-30
> 审核模式: DevSquad 4-Role dispatch (GLM-5.2 as LLM backend)
> 对照基准: DevSquad V4.4.0 (CHANGELOG 最新条目 V4.4.1 M0+M1, 2026-07-29)
> 适用范围: DevSquad 仓库所有"面向用户/开发者"的外部可见文档（含多语言版本）

---

## 一、现状审计（4-Role 视角）

### 1.1 文档清单与定位

| # | 文档路径 | 当前定位 | 实际内容 | 标注版本 | 目标读者 | 问题 |
|---|---------|---------|---------|---------|---------|------|
| 1 | `README.md` (EN) | 英文入口 | "30秒理解"+"V4.3.0 P0-P2 详解"+"V4.1.0 特性"+"5种使用方式"+"架构概览"+"7角色"+"5大能力域" | V4.4.0 | 不明确（混合初学者+老用户） | 🔴 入口文档承载特性详解；标题"EN"却含大量中文；测试数 7681/7400/5250 三种说法混入；模块数 235 与 SKILL.md 160+/186+ 矛盾 |
| 2 | `README-CN.md` (CN) | 中文入口 | V4.1.0 特性详解 + 5种使用方式 + 架构概览 + 关注点增强包 | V4.4.0 | 不明确 | 🔴 标题 V4.4.0 但内容主体是 V4.1.0；"7400+ tests"与 badge "8155" 不一致；"235 模块"与"185+ 模块"内部矛盾；中文标题却英文段落 |
| 3 | `README-JP.md` (JP) | 日文入口 | V4.1.0 特性详解 + 5种使用方式 | V4.4.0 | 不明确 | 🔴 标题 V4.4.0 但内容主体是 V4.1.0；"5250+ tests"严重过期；"185+ モジュール"与 EN 235 矛盾；日文文档含中文段 |
| 4 | `QUICKSTART.md` | 5 分钟快速入门 | 30 秒理解 + 5 分钟上手 + 7 角色 + 3 场景示例 | V4.4.0 | 初学者 | 🟡 与 README "30秒看这个"+"5分钟上手"重复；7 角色表与 README 重复 |
| 5 | `INSTALL.md` | 安装指南 | Method 0/1/5/6 + LLM 后端配置 | V4.4.0 | 部署者 | 🟡 Method 编号跳号（缺 2/3/4）；与 QUICKSTART 安装部分重复；admin/admin123 默认密码多处出现 |
| 6 | `GUIDE.md` | 完整用户指南 | 17 章节 + 3 附录，覆盖所有功能 | **V3.9.2** (2026-06-27) | 终端用户 | 🔴 **严重过期 4 个版本**；标题 V3.9.2 但 README 宣传 V4.4.0；与 docs/USAGE_GUIDE.md 部分内容重叠 |
| 7 | `EXAMPLES.md` | 使用示例 | 3 种使用方式 + 真实输出验证 | **V3.6.1** (2026-05-20 验证) | 开发者 | 🔴 **严重过期 8 个版本**；"最后验证"标 2026-05-20；与 README/QUICKSTART 重叠 |
| 8 | `docs/USAGE_GUIDE.md` | 使用指南（已标 HISTORICAL） | V3.6.0-C 分层架构 + 11 阶段 + Plan C | **V3.6.0-C** | 已被弃用 | 🔴 **已自标"已过时 (HISTORICAL)"但未删除**；占用用户注意；与 GUIDE.md 重复 |
| 9 | `docs/guides/CONFIGURATION.md` | 配置参考 | 3 种配置方法 + LLM 后端 + .devsquad.yaml | **V4.0.11** (2026-07-14) | 部署者 | 🟡 版本号旧（V4.0.11 vs V4.4.0）；位于 docs/guides/ 但 README 引用路径不明确 |
| 10 | `COMPARISON.md` | 框架对比 | DevSquad vs AutoGen/CrewAI/LangGraph | 2026-07-29 | 选型决策者 | 🟢 最新；但"E2E 27 用例"未更新为 V4.4.0 的 13+27=40+ 用例 |
| 11 | `SKILL.md` | Skill 完整参考 | 一句话理解 + 工作流 + 186+ 模块清单 | V4.4.0 | Skill 集成者 | 🟡 "160+ core modules"（frontmatter）与"186+ Core Modules"（正文）内部矛盾；与 README "235 modules" 不一致 |
| 12 | `CHANGELOG.md` (EN) | 变更日志 | V4.4.1 M0+M1 条目 | V4.4.1 | 维护者 | 🟢 最新；引用 CHANGELOG-CN.md |
| 13 | `CHANGELOG-CN.md` (CN) | 变更日志中文 | — | — | — | 🟡 未读取，假定与 EN 同步但需校验 |
| 14 | `CLAUDE.md` | Claude Code 集成 | — | — | Claude Code 用户 | 🟡 未读取；定位未明，可能与 SKILL.md 重叠 |
| 15 | `RELEASE_CHECKLIST.md` | 发布检查清单 | — | — | 维护者 | 🟡 未读取；属外部文档但未纳入审计 |
| 16 | `CONTRIBUTING.md` | 贡献指南 | — | — | 贡献者 | 🟢 标准开源文档，定位清晰 |
| 17 | `docs/i18n/EXAMPLES_EN.md` `EXAMPLES_JP.md` `GUIDE_EN.md` `GUIDE_JP.md` `QUICK_START_EN.md` `QUICK_START_JP.md` `REFERENCE_GUIDE_EN.md` `REFERENCE_GUIDE_JP.md` `SKILL_CN.md` `SKILL_JP.md` | **11 份孤儿多语言文档** | — | — | — | 🔴 **完全孤立**：根目录文档不引用；与根目录同名文档并行存在；命名不一致（QUICK_START vs QUICKSTART）；与三语言 README 体系冲突；**疑似废弃但未归档** |
| 18 | `docs/guides/QUICK_REFERENCE.md` | 快速参考 | — | — | — | 🟡 与 QUICKSTART.md 定位可能重叠 |
| 19 | `docs/operations/OPERATIONS.md` | 运维指南 | — | — | DevOps | 🟢 定位清晰 |
| 20 | `docs/ROADMAP.md` | 路线图 | — | — | 决策者 | 🟢 定位清晰 |

**关键统计**：
- 根目录 `.md` 文档：**14 份**
- docs/i18n/ 孤儿多语言文档：**10 份**
- 已识别"定位重叠"文档对：**≥6 对**
- 已识别"版本号过期"文档：**4 份**（GUIDE.md V3.9.2 / EXAMPLES.md V3.6.1 / USAGE_GUIDE.md V3.6.0-C / CONFIGURATION.md V4.0.11）
- 已识别"自标 HISTORICAL 但未删除"：**1 份**（USAGE_GUIDE.md）

### 1.2 多语言一致性审计

| 指标 | EN | CN | JP | SKILL.md | CHANGELOG.md | 一致性问题 |
|------|----|----|-----|---------|--------------|-----------|
| 标注版本 | V4.4.0 | V4.4.0 | V4.4.0 | V4.4.0 | V4.4.1 | 🟢 表面一致（但 CHANGELOG 已 V4.4.1，README 仍 V4.4.0） |
| 测试数（badge） | 8155 passing | 8155 passing | 8155 passing | 8155+ passing | — | 🟢 Badge 一致 |
| 测试数（正文） | 7681 / 7400+ / 5250+ 混用 | 7400+ | 5250+ | — | — | 🔴 **三语言正文完全不同步**；EN 内部 3 种说法并存 |
| 模块数 | 235（正文）| 235 + 185+（混用）| 185+ | 160+（frontmatter）+ 186+（正文）| — | 🔴 **至少 4 种说法**：160+ / 185+ / 186+ / 235 |
| 内容主体版本 | V4.3.0 详解 + V4.1.0 段落 | V4.1.0 | V4.1.0 | V4.4.0 | V4.4.1 | 🔴 **CN/JP 内容停留在 V4.1.0**，EN 混合 V4.3.0+V4.1.0 |
| 使用方式数量 | 5 种（Method 1-5） | 5 种 | 5 种 | — | — | 🟢 一致（但与 INSTALL.md 的 Method 0/1/5/6 不一致） |
| 角色表 | 7 角色（含权重/别名）| 7 角色（含触发关键词）| — | — | — | 🟡 同一信息三语言字段不同；CN/EN/JP 各自定义 |
| CHANGELOG | EN | CN（CHANGELOG-CN.md）| ❌ 无 JP 版 | — | — | 🔴 JP 无 CHANGELOG；多语言策略未明 |

### 1.3 4-Role 审核纪要

#### 🧑‍💼 Product-Manager 视角

**严重问题**：

1. **🔴 用户旅程断裂（Critical）**：README → QUICKSTART → GUIDE 是合理设计，但 `GUIDE.md` 停在 V3.9.2（落后 4 个版本），新用户跟随 README 进入 GUIDE 后会发现内容与 README 描述的能力域/模块数/V4.x 特性完全脱节，造成"教程在说 V3 的事，README 在说 V4 的事"的认知撕裂。

2. **🔴 入口文档定位错乱（Critical）**：`README.md` 当前混合了 4 类本不该共存的诉求：
   - 30 秒理解（入口应保留）
   - 5 分钟上手（应交给 QUICKSTART）
   - V4.3.0 P0-P2 特性详解（应交给 CHANGELOG 或发行说明）
   - V4.1.0 + V4.0.0 历史特性（应交给 CHANGELOG）
   - 5 大能力域 235 模块详解（应交给 SKILL.md 或 ARCHITECTURE 文档）

   结果：新用户 30 秒看不完，老用户找不到版本特性。

3. **🟡 目标读者未声明（High）**：14 份外部文档**没有一份**在开头明确"给谁看、解决什么问题、读完能做什么"。INSTALL.md 是唯一接近的（"Path Placeholder Notice"），但仍未声明目标读者。

4. **🟡 docs/i18n/ 11 份孤儿文档（High）**：这是一个独立翻译体系（EXAMPLES_EN/JP、GUIDE_EN/JP、QUICK_START_EN/JP、REFERENCE_GUIDE_EN/JP、SKILL_CN/JP），但根目录文档**无一处引用**它们。用户根本无法发现这套文档存在。两种可能：(a) 早期翻译尝试已废弃；(b) 是未来多语言策略的雏形。无论哪种，当前状态=浪费。

5. **🟢 QUICKSTART 设计意图正确（OK）**：30 秒 + 5 分钟 + 场景示例的递进结构符合新用户上手路径，但与 README 重叠需消减。

#### 🎨 UI-Designer 视角

**严重问题**：

1. **🔴 信息架构（IA）混乱（Critical）**：
   - 根目录扁平堆放 14 份 `.md`（README/QUICKSTART/INSTALL/GUIDE/EXAMPLES/COMPARISON/SKILL/CLAUDE/RELEASE_CHECKLIST/CONTRIBUTING/CHANGELOG/CHANGELOG-CN/README-CN/README-JP）
   - docs/ 又有平行的 USAGE_GUIDE.md、guides/CONFIGURATION.md、guides/QUICK_REFERENCE.md、guides/PONYTAIL_MARKER_GUIDE.md
   - docs/i18n/ 又有 11 份平行多语言文档
   - 用户不知道该看哪一份；同一类内容分布在 3 处（如"使用指南"在 GUIDE.md / USAGE_GUIDE.md / GUIDE_EN.md / GUIDE_JP.md 四处）

2. **🔴 视觉层次不一致（Critical）**：
   - EN README 使用 `<details><summary>` 折叠长内容
   - CN README 不使用折叠，整页铺开
   - JP README 也不折叠
   - 三语言版本视觉密度差异巨大，破坏多语言用户体验一致性

3. **🔴 入口直观性差（Critical）**：
   - 根目录前 14 个 `.md` 文件名有 7 种命名风格：`README.md` / `README-CN.md` / `README-JP.md`（连字符）；`CHANGELOG.md` / `CHANGELOG-CN.md`（连字符）；`QUICKSTART.md`（无连字符）；`INSTALL.md` / `GUIDE.md` / `EXAMPLES.md` / `COMPARISON.md` / `SKILL.md`（全大写单词）；`CLAUDE.md` / `CONTRIBUTING.md` / `RELEASE_CHECKLIST.md`（下划线分隔）
   - `docs/i18n/` 用 `QUICK_START_EN.md`（下划线） vs 根目录 `QUICKSTART.md`（无下划线）— 同一概念两种命名

4. **🟡 多语言交叉污染（High）**：
   - EN `README.md` 大量中文段（"太长不看？先看这个（30 秒）"、"🚀 V4.3.0..."）
   - CN `README-CN.md` 大量英文段（"Quick Start (5 Ways to Use DevSquad)"、"## 👥 7 Core Roles"）
   - JP `README-JP.md` 也含中文段（"巡検"、"防护"等）
   - 这是"半翻译"状态，违反多语言文档基本原则

5. **🟡 重复信息块（High）**：7 角色表在 README/QUICKSTART/GUIDE/SKILL 至少 4 处出现，字段还不一致（EN 给权重+别名，CN 给触发关键词，JP 不给）。

#### 🏗️ Architect 视角

**严重问题**：

1. **🔴 版本号同步严重失守（Critical）**：

   | 文档 | 标注版本 | 距离 V4.4.0 |
   |------|---------|-----------|
   | README.md / README-CN.md / README-JP.md | V4.4.0 | 0（标题）但正文仍 V4.1.0/V4.3.0 |
   | QUICKSTART.md | V4.4.0 | 0 |
   | INSTALL.md | V4.4.0 | 0 |
   | SKILL.md | V4.4.0 | 0 |
   | COMPARISON.md | 2026-07-29 | 0 |
   | CHANGELOG.md | V4.4.1 | -1（最新） |
   | **CONFIGURATION.md** | **V4.0.11** | **-4 minor** |
   | **GUIDE.md** | **V3.9.2** | **-5 minor** |
   | **EXAMPLES.md** | **V3.6.1** | **-8 minor** |
   | **USAGE_GUIDE.md** | **V3.6.0-C** | **-8 minor**（已标 HISTORICAL） |

   `check_doc_consistency.sh` 已存在但显然未覆盖版本号字段（仅 11/11 PASS 但 README 三版本测试数/模块数都不同步却仍 PASS）。

2. **🔴 模块数 4 种说法（Critical）**：
   - README.md：**235 modules**（Domain 4 段）
   - README-CN.md：**235 模块** + 后文 **185+ 模块**（自相矛盾）
   - README-JP.md：**185+ モジュール**
   - SKILL.md frontmatter：**160+ core modules**
   - SKILL.md 正文：**186+ Core Modules**
   - 与实际代码库模块数完全脱钩，无人校验

3. **🔴 测试数 4 种说法（Critical）**：
   - Badge（三语言）：8155 passing
   - README.md 正文：**7681 tests passing**（V4.3.0 段）+ **7400+ tests passing**（V4.1.0 段）+ **5250+ tests passing**（历史段）
   - README-CN.md：**7400+ tests passing**
   - README-JP.md：**5250+ tests passing**
   - SKILL.md：**8155+ tests passing**
   - 同一文档 EN README 内部 3 种说法并存

4. **🟡 文档与代码一致性失守（High）**：
   - INSTALL.md 写 `devsquad dispatch -t "..."` 但 Method 编号跳号（0/1/5/6），暗示"Method 2/3/4"被删除但未重新编号
   - README 引用 `[185+ 模块详细参考](SKILL.md)` 但 SKILL.md 实际是 "186+ Core Modules"
   - CHANGELOG 提到 `check_module_activation.py` 已被 E2E 测试 E13 替代，但 README/GUIDE 中是否仍有引用未审计

5. **🟡 技术深度错位（High）**：
   - README.md 用大段篇幅讲 V4.3.0 P0-P2 实施细节（"P0-1 pickle→JSON 迁移阶段 1"、"P1-4 LoopKernel RollbackStrategy"）— 这是 CHANGELOG 内容，不是 README
   - GUIDE.md 停在 V3.9.2 但 README 宣传 V4.4.0 的 5 大能力域、Ponytail/LoopKernel/Error Budget 等模块 — 用户读 GUIDE 完全无法理解这些

6. **🟢 COMPARISON.md / SKILL.md 是健康样板（OK）**：相对新、相对一致，可作为其他文档重构的参照。

#### 💻 Solo-Coder 视角

**严重问题**：

1. **🔴 代码示例可能无法运行（Critical）**：
   - `EXAMPLES.md` 标注"最后验证: 2026-05-20, DevSquad V3.6.1, backend=openai, model=gpt-4"
   - 但 V4.4.0 引入了 Risk Register / Viewpoint Registry / Error Budget / Gap Analyzer / DORA Metrics 5 个新模块
   - EXAMPLES 完全没有覆盖这 5 个模块的示例 — 用户不知道如何调用
   - `OPENAI_BASE_URL="https://api.moka-ai.com/v1"` 这种第三方代理配置散落文档中

2. **🔴 安装步骤编号断裂（Critical）**：
   - `INSTALL.md` 提供 "Method 0: Interactive Setup Wizard" / "Method 1: CLI" / "Method 5: Web Dashboard" / "Method 6: REST API Server"
   - Method 2/3/4 完全缺失 — 用户会以为漏看了内容
   - 这是合并/删除后的残留，未做编号重整

3. **🔴 默认凭证在多文档重复（Critical 安全问题）**：
   - README.md / README-CN.md / README-JP.md / QUICKSTART.md / INSTALL.md / EXAMPLES.md **6 处**重复出现 `admin / admin123` `operator / operator123` `viewer / viewer123`
   - 任一处忘记"生产环境必须改密码"提示就是漏洞
   - 应统一到 INSTALL.md 一处 + 强提示

4. **🟡 配置项零散（High）**：
   - LLM 后端配置在 README/INSTALL/EXAMPLES/CONFIGURATION 四处出现
   - `DEVSQUAD_LLM_BACKEND` 在 README 用 `auto`，INSTALL 用 `openai`，CONFIGURATION 用 `auto` — 不一致
   - Mock 模式说明分散：QUICKSTART 不提，INSTALL 说"默认 mock 模式"，EXAMPLES 说"默认 mock 模式"

5. **🟡 错误排查指引缺失（High）**：
   - GUIDE.md 第 17 章是"常见问题"，但版本 V3.9.2 — V4.x 的报错（如 backend 不存在、模块未激活、checkpoint 损坏）无排查指引
   - INSTALL.md 没有"安装失败怎么办"
   - QUICKSTART 没有"第一次跑出错了"

6. **🟢 SKILL.md 的模块清单可执行性较好（OK）**：每个模块给了文件名和职责，便于开发者直接定位代码。

### 1.4 审计小结（4-Role 共识）

| 维度 | 严重度 | 问题数 | 关键发现 |
|------|-------|-------|---------|
| 用户旅程完整性 | 🔴 Critical | 3 | GUIDE/EXAMPLES 严重过期；README 入口承载特性详解；目标读者未声明 |
| 多语言一致性 | 🔴 Critical | 4 | 测试数 4 种说法；模块数 4 种说法；CN/JP 内容停留在 V4.1.0；docs/i18n 11 份孤儿文档 |
| 信息架构 | 🔴 Critical | 2 | 14 份根目录扁平堆放；3 处平行内容（根/docs/docs/i18n） |
| 视觉层次 | 🔴 Critical | 2 | 折叠策略三语言不一致；命名风格 7 种 |
| 版本号同步 | 🔴 Critical | 1 | 4 份文档版本号旧（V3.6.0-C/V3.6.1/V3.9.2/V4.0.11） |
| 文档与代码一致性 | 🟡 High | 2 | INSTALL Method 跳号；模块数与实际代码库脱钩 |
| 代码示例可运行性 | 🔴 Critical | 2 | EXAMPLES V3.6.1 严重过期；V4.4.0 新模块无示例 |
| 安全 | 🟡 High | 1 | 默认凭证 6 处重复 |
| 错误排查指引 | 🟡 High | 1 | V4.x 报错无排查 |

**结论：当前外部文档体系处于"严重凌乱"状态，无法支撑 V4.4.0 的对外宣传。必须重构。**

---

## 二、重构原则

### 原则 1：文档分层（用户旅程驱动）

```
入口（README，30 秒）
  ↓
快速入门（QUICKSTART，5 分钟）
  ↓
安装（INSTALL，可执行）
  ↓
完整指南（GUIDE，按需查阅）
  ↓
深度参考（SKILL / CONFIGURATION / COMPARISON）
  ↓
变更日志（CHANGELOG，按需查阅）
```

每层只回答一个核心问题：
- README：**DevSquad 是什么？为什么用？**
- QUICKSTART：**5 分钟怎么跑起来？**
- INSTALL：**完整安装/部署怎么做？**
- GUIDE：**每个功能怎么用？**
- SKILL：**作为 Skill 怎么集成？**
- CONFIGURATION：**所有配置项参考**
- COMPARISON：**和别的框架比怎么选？**
- CHANGELOG：**每个版本变了什么？**

### 原则 2：多语言同步策略

**只对"入口级"文档做三语言**（EN/CN/JP），其他文档仅 EN，避免过度翻译：
- ✅ 三语言：`README.md` / `README-CN.md` / `README-JP.md`
- ❌ 单语言（EN）：QUICKSTART / INSTALL / GUIDE / EXAMPLES / CONFIGURATION / COMPARISON / SKILL / CHANGELOG / CONTRIBUTING / RELEASE_CHECKLIST

**理由**：
- 三语言维护成本是 3 倍；当前 CN/JP 已严重滞后正是因为维护负担过重
- 用户拿到 INSTALL/GUIDE 等技术文档时通常愿意用翻译机读 EN
- 真正需要"零摩擦上手"的只有 README — 这是入口直觉
- CHANGELOG 翻译无意义（机器可读 + 翻译机足够）

**被拒绝方案 D-1**（见第五节）：所有文档三语言 — 拒绝。

### 原则 3：版本号一致性硬约束

**所有外部文档 frontmatter 必须包含**：
```yaml
---
version: 4.4.0          # 必须与 src/devsquad/__init__.py 一致
updated: 2026-07-30
tests: 8155             # 必须与 CI 最新一致
modules: 186            # 必须与代码库实际模块数一致
---
```

**扩展 `check_doc_consistency.sh`**（已有 11/11 PASS，但显然不查版本号字段）：
- 新增检查项：扫描所有 `.md` frontmatter 中的 `version` / `tests` / `modules` 三个字段
- 与 `src/devsquad/__init__.py` `__version__` 和 CI 测试报告对比
- 不一致 = CI 失败（阻断合并）
- 排除目录：`docs/_archive/` / `docs/audits/` / `docs/planning/` / `docs/analysis/`

### 原则 4：活文档原则

- 任何代码变更涉及用户可见行为时，对应文档必须同 commit 修改
- PR 模板新增 checkbox："是否更新了用户文档？"
- 季度文档审计：检查所有外部文档的版本号一致性

### 原则 5：不过度设计（user_profile 硬约束）

- **不**为每个角色/每个能力域建独立文档
- **不**为每个版本建独立发行说明（CHANGELOG 一份足够）
- **不**保留已标"HISTORICAL"的文档（删除或归档到 docs/_archive/）
- **不**新建 docs/user_guide/ docs/manual/ 等多级子目录
- 任何新文档必须回答："解决什么用户问题？谁会读？读完能做什么？" — 答不上来就不创建

---

## 三、目标文档结构（重构后）

```
DevSquad/
├── README.md            # 入口（EN）— 30 秒理解 + 5 分钟上手链接 + 3 语言切换
├── README-CN.md         # 入口（CN）— 与 EN 严格同步
├── README-JP.md         # 入口（JP）— 与 EN 严格同步
├── QUICKSTART.md        # 5 分钟快速入门（EN only）
├── INSTALL.md           # 完整安装指南（EN only）
├── GUIDE.md             # 完整用户指南（EN only，合并 docs/USAGE_GUIDE.md）
├── EXAMPLES.md          # 示例集（EN only，含 V4.4.0 新模块示例）
├── CONFIGURATION.md     # 配置参考（EN only，从 docs/guides/ 上移到根目录）
├── COMPARISON.md        # 框架对比（EN only）
├── SKILL.md             # Skill 完整参考（EN only）
├── CHANGELOG.md         # 变更日志（EN only，删除 CHANGELOG-CN.md）
├── CONTRIBUTING.md      # 贡献指南（EN only）
├── CLAUDE.md            # Claude Code 集成（EN only，定位待澄清）
├── RELEASE_CHECKLIST.md # 发布检查清单（EN only，内部使用）
└── docs/
    ├── _archive/        # 历史归档
    │   └── USAGE_GUIDE.md  # ← 从 docs/ 移入（已标 HISTORICAL）
    ├── i18n/_archive/   # ← 新建，归档 11 份孤儿文档
    │   ├── EXAMPLES_EN.md
    │   ├── EXAMPLES_JP.md
    │   ├── GUIDE_EN.md
    │   ├── GUIDE_JP.md
    │   ├── QUICK_START_EN.md
    │   ├── QUICK_START_JP.md
    │   ├── REFERENCE_GUIDE_EN.md
    │   ├── REFERENCE_GUIDE_JP.md
    │   ├── SKILL_CN.md
    │   └── SKILL_JP.md
    ├── guides/          # ← 仅保留开发者向深度指南
    │   ├── PONYTAIL_MARKER_GUIDE.md
    │   ├── agent_briefing_confidence_integration.md
    │   └── user_onboarding_verification.md
    ├── architecture/    # 内部架构文档
    ├── operations/       # 运维文档
    ├── planning/         # 规划文档
    ├── analysis/         # 分析文档（本文件所在）
    ├── audits/           # 审计文档
    ├── adr/              # 架构决策记录
    ├── roles/            # 角色模板
    ├── spec/             # 规范文档
    ├── testing/          # 测试计划
    ├── prd/              # PRD
    ├── release/          # 发布报告
    ├── research/         # 研究
    ├── ROADMAP.md
    ├── TECH_DEBT.md
    └── ...
```

### 每份外部文档的明确定位

| 文档 | 定位 | 目标读者 | 内容边界 | 多语言策略 |
|------|------|---------|---------|-----------|
| **README.md** | 30 秒理解 DevSquad 是什么 + 选择继续深入的入口 | 首次访客（开发者/技术决策者） | 仅含：1 句话定位 / 3 秒对比表 / 5 分钟上手链接 / 3 语言切换 / 链接到 QUICKSTART+SKILL+CHANGELOG | EN/CN/JP 三语言严格同步 |
| **README-CN.md / README-JP.md** | 中文/日文入口 | 中文/日文首次访客 | 与 EN README 一一对应，不增不减 | 严格同步 |
| **QUICKSTART.md** | 5 分钟跑起来第一个任务 | 第一次安装的用户 | 仅含：5 分钟 3 步（安装→dispatch→看输出）+ 1 个真实示例 + "下一步"链接到 GUIDE | EN only |
| **INSTALL.md** | 完整安装/部署参考 | 部署者/运维 | 仅含：前置条件 / 5 种安装方式（重整编号 1-5）/ LLM 后端配置 / 生产环境配置 / 故障排查 | EN only |
| **GUIDE.md** | 完整用户指南 | 终端用户（按需查阅） | 17 章节 + 附录；合并 docs/USAGE_GUIDE.md 的 V3.6.0-C 历史内容到 _archive | EN only |
| **EXAMPLES.md** | 可运行示例集 | 开发者 | 含 V4.4.0 新模块示例（Risk Register / Viewpoint Registry / Error Budget / Gap Analyzer / DORA Metrics）；每个示例标注验证日期+版本 | EN only |
| **CONFIGURATION.md** | 配置项参考 | 部署者/集成者 | 所有配置项的权威参考；从 docs/guides/CONFIGURATION.md 上移到根目录 | EN only |
| **COMPARISON.md** | 框架对比 | 选型决策者 | DevSquad vs AutoGen/CrewAI/LangGraph；含 E2E 用例数等指标（与 SKILL.md 同步） | EN only |
| **SKILL.md** | Skill 完整参考 | Skill 集成者（Trae IDE 用户） | 186+ 模块清单 + Skill manifest + 集成方法 | EN only |
| **CHANGELOG.md** | 变更日志 | 维护者/升级用户 | Keep a Changelog 格式；保留 EN only | EN only |
| **CONTRIBUTING.md** | 贡献指南 | 开源贡献者 | 标准开源文档 | EN only |
| **RELEASE_CHECKLIST.md** | 发布检查清单 | 维护者（内部） | 发布前检查项 | EN only |
| **CLAUDE.md** | Claude Code 集成 | Claude Code 用户 | **待澄清**：与 SKILL.md 的关系（建议：CLAUDE.md 仅含 Claude Code 特定集成步骤，通用 Skill 内容引用 SKILL.md） | EN only |

### 多语言同步策略（细化）

```
EN README.md （权威源）
    ↓ 翻译机辅助 + 人工校对
CN README-CN.md
    ↓ 翻译机辅助 + 人工校对
JP README-JP.md
```

**同步规则**：
- EN README.md 是 single source of truth
- 任何 EN 修改 → 同 PR 必须更新 CN/JP（CI 强制检查）
- CN/JP 仅做语言适配（如术语本地化），不增删技术内容
- 三版本必须包含完全相同的：版本号 / 测试数 / 模块数 / 角色表 / 能力域表 / 链接目标

---

## 四、迁移计划

### 阶段 1：清理与合并（V4.4.2，1-2 天）

**目标**：删除/归档过期内容，消除最严重的认知混乱。

| 任务 | 操作 | 责任角色 | 验证 |
|------|------|---------|------|
| T1.1 归档 docs/USAGE_GUIDE.md | 移动到 `docs/_archive/USAGE_GUIDE_V3.6.0-C.md`（已标 HISTORICAL，无需保留在主路径） | solo-coder | 移动后 `docs/USAGE_GUIDE.md` 不存在；README 不引用它 |
| T1.2 归档 docs/i18n/ 11 份孤儿文档 | 创建 `docs/i18n/_archive/`，全部移入 | architect | 移动后 `docs/i18n/` 仅含 `_archive/`；根目录文档无引用断裂 |
| T1.3 删除 CHANGELOG-CN.md | 内容并入 CHANGELOG.md（如必要保留双语 changelog，改为机器可读格式） | solo-coder | CHANGELOG.md EN only；README-JP 不再引用 CHANGELOG-JP |
| T1.4 重整 INSTALL.md Method 编号 | Method 0/1/5/6 → Method 1-5（5 种方式连续编号） | solo-coder | Method 编号连续无跳号 |
| T1.5 统一默认凭证提示 | 仅 INSTALL.md 一处出现 admin/admin123；其他文档改为"参见 INSTALL.md 安全配置章节" | solo-coder + security | 全仓库 grep "admin123" 仅命中 INSTALL.md |
| T1.6 修复 GUIDE.md / EXAMPLES.md / CONFIGURATION.md 版本号 | frontmatter 更新到 V4.4.0；正文内容暂不重写（阶段 2） | architect | `check_doc_consistency.sh` 新增版本号检查通过 |

**阶段 1 验收标准**：
- ✅ `docs/USAGE_GUIDE.md` 不存在（已归档）
- ✅ `docs/i18n/` 下无活跃文档（全部归档）
- ✅ `CHANGELOG-CN.md` 不存在
- ✅ INSTALL.md Method 编号 1-5 连续
- ✅ 全仓库 grep `admin123` 仅命中 INSTALL.md + RELEASE_CHECKLIST.md
- ✅ 所有外部文档 frontmatter `version: 4.4.0`

### 阶段 2：内容重写（V4.5.0，3-5 天）

**目标**：按重构原则 1-5 重写所有外部文档内容。

| 任务 | 操作 | 责任角色 | 验证 |
|------|------|---------|------|
| T2.1 重写 README.md（EN） | 移除 V4.3.0/V4.1.0/V4.0.0 特性详解（移入 CHANGELOG）；保留 30 秒理解 + 5 分钟上手 + 入口链接 | product-manager + ui-designer | README ≤ 150 行；首屏 30 秒可读完；无版本特性详解 |
| T2.2 同步 README-CN.md / README-JP.md | 严格按 EN 翻译，三版本同结构同内容 | ui-designer | 三版本行数差 ≤ 10%；版本号/测试数/模块数完全一致 |
| T2.3 重写 QUICKSTART.md | 删除与 README 重复的 7 角色表；保留 3 步 5 分钟 + 1 真实示例 + 下一步链接 | product-manager | ≤ 100 行；用户 5 分钟可跑出第一个输出 |
| T2.4 重写 GUIDE.md | 基于 V4.4.0 重写；新增 V4.4.0 5 个新模块章节；移除已废弃内容 | architect | GUIDE.md frontmatter V4.4.0；章节覆盖 5 大能力域全部模块 |
| T2.5 重写 EXAMPLES.md | 基于 V4.4.0 重写；新增 Risk Register / Viewpoint Registry / Error Budget / Gap Analyzer / DORA Metrics 示例 | solo-coder | 每个示例标注"验证于 YYYY-MM-DD, V4.4.0, backend=mock"；至少 1 个示例覆盖每个 V4.4.0 新模块 |
| T2.6 上移 CONFIGURATION.md | 从 `docs/guides/CONFIGURATION.md` 移到根目录 `CONFIGURATION.md`；更新到 V4.4.0 | architect | 根目录存在 CONFIGURATION.md；docs/guides/ 下不再有 |
| T2.7 统一模块数与测试数 | 全仓库 grep 替换：模块数统一为实际值（用 `find src -name "*.py" | wc -l` 校验）；测试数统一为 CI 最新值 | architect | `check_doc_consistency.sh` 新增检查通过 |
| T2.8 澄清 CLAUDE.md 定位 | 与 SKILL.md 对比；CLAUDE.md 仅含 Claude Code 特定集成步骤 | architect | CLAUDE.md 与 SKILL.md 无内容重叠 |

**阶段 2 验收标准**：
- ✅ README.md ≤ 150 行
- ✅ 三语言 README 完全同步（version/tests/modules 一致）
- ✅ GUIDE.md / EXAMPLES.md / CONFIGURATION.md 全部 V4.4.0
- ✅ EXAMPLES.md 覆盖 V4.4.0 全部 5 个新模块
- ✅ 模块数全仓库统一（1 种说法）
- ✅ 测试数全仓库统一（1 种说法）
- ✅ `check_doc_consistency.sh` 扩展检查项全部通过

### 阶段 3：CI 自动化保障（V4.5.0，1 天）

**目标**：防止文档再次失同步。

| 任务 | 操作 | 责任角色 | 验证 |
|------|------|---------|------|
| T3.1 扩展 check_doc_consistency.sh | 新增：扫描所有外部 .md frontmatter 的 version/tests/modules 字段；与 `__init__.py __version__` 对比 | architect | CI 失败时给出具体不一致的文件+字段 |
| T3.2 新增 multilang_sync_check.py | 校验 README.md / README-CN.md / README-JP.md 三版本的 version/tests/modules 字段完全一致 | architect | 三版本任一不一致即 CI 失败 |
| T3.3 PR 模板新增 checkbox | "本 PR 是否更新了用户可见文档？如否，请说明理由" | product-manager | PR 模板生效 |
| T3.4 E2E 测试新增文档校验 | 新增 `test_external_docs_consistency.py`：读取所有外部 .md，断言关键指标一致 | solo-coder | E2E 测试通过 |

**阶段 3 验收标准**：
- ✅ `check_doc_consistency.sh` 覆盖版本号字段
- ✅ `multilang_sync_check.py` 通过
- ✅ PR 模板含文档 checkbox
- ✅ E2E 测试覆盖文档一致性

### 阶段 4：发布前 E2E 验证（V4.5.0 发布前）

**遵循 user_profile 硬约束**：发布前必须做模拟真实用户使用的测试。

| 测试场景 | 操作 | 预期 | 责任角色 |
|---------|------|------|---------|
| 新用户 30 秒理解 | 仅看 README 首屏，能复述 DevSquad 是什么、解决什么 | ≤ 30 秒回答 | product-manager |
| 新用户 5 分钟上手 | 按 QUICKSTART 跑出第一个 dispatch 输出 | ≤ 5 分钟 | solo-coder |
| 部署者安装 | 按 INSTALL.md 完成 5 种安装方式 | 全部成功 | solo-coder |
| 用户查指南 | 按 GUIDE.md 找到 V4.4.0 新模块用法 | ≤ 3 分钟定位 | architect |
| 用户查示例 | 按 EXAMPLES.md 跑通 V4.4.0 新模块示例 | 全部通过 | solo-coder |
| 多语言切换 | EN→CN→JP 切换 README，技术指标完全一致 | 三版本同字段同值 | ui-designer |
| 选型决策 | 按 COMPARISON.md 决策树选择框架 | 决策树无歧义 | product-manager |

---

## 五、被拒绝的方案及理由

### D-1：所有外部文档三语言化 ❌ 拒绝

**提案**：QUICKSTART / INSTALL / GUIDE / EXAMPLES / CONFIGURATION / SKILL / CHANGELOG 全部三语言。

**拒绝理由**：
- 维护成本 3 倍，当前 CN/JP 已严重滞后正是证明
- 用户拿到 INSTALL/GUIDE 等技术文档时通常愿意用翻译机读 EN
- 真正需要"零摩擦上手"的只有 README — 这是入口直觉
- CHANGELOG 翻译无意义（机器可读 + 翻译机足够）
- 违反"不过度设计"原则

### D-2：将所有文档迁到 docs/ 子目录 ❌ 拒绝

**提案**：根目录只留 README.md，其他全部移到 docs/user/。

**拒绝理由**：
- 破坏 GitHub 入口直觉（用户访问 repo 主页第一眼看到的是根目录 README + 文件列表）
- QUICKSTART.md / INSTALL.md / GUIDE.md 等是 GitHub 用户期待的根目录标准文件
- docs/ 子目录已用于内部文档（architecture/planning/analysis 等），混入用户文档会进一步加重 IA 混乱
- 违反"不过度设计"原则

### D-3：每份文档加 V4.4.0 特性详解 ❌ 拒绝

**提案**：README / QUICKSTART / GUIDE / EXAMPLES 都加 V4.4.0 5 个新模块的详解。

**拒绝理由**：
- README 不应承载特性详解（这是 CHANGELOG 的职责）
- QUICKSTART 是 5 分钟跑起来，不是特性介绍
- 详解只在 GUIDE / EXAMPLES / SKILL 三处出现（按读者需求分层）
- 违反"文档分层"原则

### D-4：保留 docs/i18n/ 11 份孤儿文档并完善 ❌ 拒绝

**提案**：将 docs/i18n/ 作为多语言文档的主体系，根目录只保留 EN。

**拒绝理由**：
- 11 份文档当前完全无引用，是孤立资产
- 命名风格与根目录冲突（QUICK_START vs QUICKSTART）
- 与本计划"README 三语言 + 其他 EN only"策略冲突
- 维护负担过重（违反"不过度设计"原则）
- 已决定归档到 `docs/i18n/_archive/`，未来如需重启多语言体系，从 _archive 取出 + 系统化重做

### D-5：将 CHANGELOG 拆成多语言 ❌ 拒绝

**提案**：保留 CHANGELOG-CN.md，新增 CHANGELOG-JP.md。

**拒绝理由**：
- CHANGELOG 是机器可读 + 翻译机足够
- 三语言维护成本不值得
- 当前 CHANGELOG-CN.md 已存在但同步状态未校验 — 反而是失同步风险源
- 决定：删除 CHANGELOG-CN.md，仅保留 EN

### D-6：每份文档加详细错误排查章节 ❌ 拒绝

**提案**：README / QUICKSTART / INSTALL / GUIDE 都加"常见问题"章节。

**拒绝理由**：
- 错误排查只在 GUIDE.md 一处（17 章已存在，需重写到 V4.4.0）
- INSTALL.md 加"安装失败怎么办"短章节
- 其他文档不重复
- 违反"不过度设计"原则

### D-7：新建 docs/user_guide/ 多级目录 ❌ 拒绝

**提案**：将所有用户文档移到 docs/user_guide/，按角色分文件。

**拒绝理由**：
- 多级目录增加用户查找成本
- 当前 14 份根目录 .md 已是行业标准（GitHub 生态惯例）
- 应做的是"减少文档数 + 明确每份定位"，而非"增加目录层级"
- 违反"不过度设计"原则

---

## 六、共识签署

### 4-Role 共识确认

| 角色 | 签署 | 备注 |
|------|------|------|
| 🧑‍💼 **Product Manager** | ✅ APPROVE | 同意用户旅程重构（README→QUICKSTART→GUIDE→SKILL）；同意三语言仅限 README；同意删除 docs/i18n/ 孤儿文档 |
| 🎨 **UI Designer** | ✅ APPROVE | 同意 IA 重整（14 份根目录扁平 → 明确定位）；同意视觉层次统一（折叠策略三语言一致）；同意命名风格统一 |
| 🏗️ **Architect** | ✅ APPROVE | 同意版本号硬约束（扩展 check_doc_consistency.sh）；同意模块数/测试数全仓库统一；同意 CONFIGURATION.md 上移根目录 |
| 💻 **Solo-Coder** | ✅ APPROVE | 同意 INSTALL Method 重新编号；同意默认凭证收敛到 INSTALL 一处；同意 EXAMPLES 新增 V4.4.0 模块示例 |

### 风险与限制

1. **阶段 2 工作量大**：GUIDE.md / EXAMPLES.md 需基于 V4.4.0 完全重写，预计 3-5 天。可考虑拆分为 V4.5.0 多个 minor PR。
2. **docs/i18n/ 归档可能影响历史引用**：归档前需 grep 全仓库确认无活跃引用（CI 链接检查）。
3. **CHANGELOG-CN.md 删除需告知现有读者**：在 CHANGELOG.md 顶部加一句"中文版已停更，请使用翻译机"。
4. **CLAUDE.md 定位待澄清**：需与 Claude Code 用户确认当前使用方式，再决定保留/合并/删除。

### 后续行动

- 本计划提交后，创建 `docs/planning/V4.5.0_DOCS_ROADMAP.md` 细化阶段 1-3 任务为具体 issue
- 阶段 1 任务（T1.1-T1.6）可立即开始，不依赖 V4.5.0 发布
- 阶段 2 任务（T2.1-T2.8）需在 V4.5.0 开发周期内完成
- 阶段 3 任务（T3.1-T3.4）需在 V4.5.0 发布前完成
- 阶段 4 E2E 验证在 V4.5.0 release candidate 阶段执行

---

**文档结束**

> 本文档遵循 DevSquad 活文档原则：随代码与文档体系演进定期复审。下次复审触发条件：(1) V4.5.0 发布前；(2) 文档结构发生重大调整时；(3) 用户反馈文档混乱时。
