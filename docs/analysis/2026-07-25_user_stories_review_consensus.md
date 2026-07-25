# DevSquad V4.3.0 用户故事评审共识报告

> **评审日期**: 2026-07-25
> **评审对象**:
> - [DevSquad V4.3.0 用户故事](./2026-07-25_user_stories_by_lifecycle.md)（35 个用户故事，11 阶段生命周期）
> - [SDLC 痛点分析](./2026-07-25_SDLC_pain_points_analysis.md)（80 个痛点，30 已解决 / 18 部分 / 17 未解决）
> **评审方法**: 7 角色并行评审 + 加权共识投票 + 否决权机制
> **核心约束**:
> - 增强功能必须被 DevSquad Skill 自然地在项目生命周期中调用到，**禁止成为幽灵功能**
> - **稳扎稳打**，不追求快速胜利
> - **测试场景骨架先行**（用户认可的良好实践）

---

## 一、评审背景与目标

### 1.1 评审触发

用户在审阅用户故事文档后，提出 3 个关键要求：

1. **防幽灵功能**：增强功能要被 DevSquad 的 Skill 自然地在项目生命周期中调用到，而不是成为孤儿模块
2. **稳扎稳打**：不追求快速胜利（推翻原 Wave 1 "DependencyHallucinationChecker 快速胜利"策略）
3. **骨架先行**：建立测试场景骨架是个很好的实践（认可原方案的 E2E 骨架思路）

### 1.2 评审目标

| 目标 | 衡量标准 |
|------|---------|
| 防幽灵功能 | 每个新模块必须明确 Skill 调用链集成点，无孤儿模块 |
| 稳扎稳打 | 每个 Phase 完成后必须通过门禁，不允许带病推进 |
| 骨架先行 | 测试场景骨架先于模块实现，作为验收基准 |
| 全局视角 | 7 角色达成共识，无否决项 |
| 可执行性 | 推进方案有明确的文件路径、验证命令、Skill 集成点 |

### 1.3 评审方法

```
7 角色并行评审 → 各角色出具意见 → 加权共识投票 → 否决权检查 → 共识结论
     ↓                ↓                ↓              ↓            ↓
  独立视角       提出异议/补充       权重 0.30/0.25/0.20/0.15/0.10   安全角色一票否决   修订方案
```

**权重分配**（与 FiveAxisConsensusEngine 一致）：
- 架构师 0.30 / 安全 0.25 / PM 0.20 / 测试 0.15 / 开发 0.10（DevOps/UI 各 0.05 加权到主角色）

---

## 二、7 角色评审意见

### 2.1 架构师视角（权重 0.30）

#### 2.1.1 评审结论：**CONDITIONAL APPROVE**（附 3 项必须修改条件）

#### 2.1.2 评审意见

**优点认可**：
- 35 个用户故事按 11 阶段生命周期组织，结构清晰
- 三档分类（已解决/部分解决/未解决）+ 优先级矩阵，决策依据充分
- E2E 验证点设计到位，每个用户故事都有可观察的验收标准

**问题 1：4 个新模块缺乏 Skill 调用链设计（P0，必须修改）**

原方案只说"新建模块"，没说"如何被 Skill 调用"。DevSquad 历史教训：
- V3.9 之前有 19 个孤立原型（~5000 行幽灵代码）
- V4.0.0 升级时强调"无幽灵功能"，每个新模块都集成到 dispatch pipeline

**要求**：每个新模块必须明确：
1. 集成到哪个 Skill（dispatch/intent/review/security/test/retrospective 之一）
2. 在 dispatch pipeline 的哪个阶段触发（pre-worker / post-worker / post-dispatch / lifecycle gate）
3. 通过哪个 dispatcher 公共 API 暴露（如 `dispatch_with_loop()` / `qa_audit_url()` 模式）

**问题 2：Wave 1 节奏过快，违反"稳扎稳打"（P1，必须修改）**

原 Wave 1 计划 2-3 周完成 5 个用户故事 + 4 个新模块，节奏过快。建议：
- Phase 0 先建立测试骨架（1 周）
- Phase 1 实现 1 个新模块 + Skill 集成（2 周）
- Phase 2 实现 1 个新模块 + Skill 集成（2 周）
- 每个 Phase 完成后必须通过门禁（覆盖率/CI/E2E 全绿）

**问题 3：缺乏"集成验证"环节（P1，必须修改）**

原方案 Wave 1 验收只有"4 个新模块单元测试覆盖率 ≥80%"，没有"集成到 dispatch pipeline 后 E2E 通过"。要求增加：
- 新模块集成后，dispatch pipeline 的现有 E2E 测试 100% 通过（零回归）
- 新增至少 2 个 E2E 测试覆盖新模块的 Skill 调用链
- SKILL.md 模块表更新（模块数 +1，测试数 +N）

#### 2.1.3 防幽灵功能建议

| 新模块 | Skill 集成点 | dispatcher API | 触发阶段 |
|--------|------------|---------------|---------|
| `DependencyHallucinationChecker` | `SecuritySkill` 扩展 | `security_scan_dependencies(code)` | P8 实现阶段 post-worker |
| `OutputValidator` | `dispatch` pipeline 扩展 | dispatcher 自动调用（post-worker hook） | P8 实现阶段 post-worker |
| `DeploymentComplianceChecker` | `dispatch` lifecycle gate | `lifecycle_gate_check(phase=P10, target_env)` | P10 部署阶段门禁 |
| `BenchmarkRegressionChecker` | `dispatch` lifecycle gate + nightly CI | `lifecycle_gate_check(phase=P11, baseline_version)` | P11 运维阶段门禁 |

---

### 2.2 产品经理视角（权重 0.20）

#### 2.2.1 评审结论：**APPROVE**（附 2 项建议）

#### 2.2.2 评审意见

**优点认可**：
- 视角转换到位（从"DevSquad 自身"到"用户手头项目"）
- 用户角色画像准确（PM/开发者/项目负责人/运维负责人，符合用户一人多角色现实）
- 优先级权衡合理（安全 > 质量 > 效能 > 体验）

**建议 1：用户故事粒度偏细，建议按"用户旅程"重组（P2）**

35 个用户故事按 SDLC 阶段组织，但用户实际使用是按"旅程"组织的。建议补充用户旅程视角：
- 旅程 A：PM 澄清需求 → 架构评审 → 任务拆解（覆盖 US-P1-001/002/003 + US-P2-001/004 + US-P3-002）
- 旅程 B：开发者写代码 → 审查 → 测试（覆盖 US-P8-001/002/004 + US-P9-001/002）
- 旅程 C：运维部署 → 监控 → 回滚（覆盖 US-P10-001/002/004 + US-P11-001/002）

**建议 2：真实用户模拟测试需要更具体的招募标准（P2）**

原方案"邀请 3-5 位真实用户"过于宽泛。建议明确：
- 用户画像：技术栈匹配（Python/前端/运维）、经验级别（初中高级搭配）
- 任务真实性：必须用用户手头的真实项目，不用玩具示例
- 反馈结构化：用 Net Promoter Score（NPS）+ 任务完成率 + 痛点排名

#### 2.2.3 防幽灵功能建议

从 PM 视角，"幽灵功能"= 用户感知不到的功能。要求每个新模块必须：
1. 在 SKILL.md 用户文档中有明确的"何时使用"说明
2. 在 `devsquad run` 输出的报告中有可见的"该功能已触发"标记
3. 用户可通过 `devsquad status` 查看该功能的调用次数和效果

---

### 2.3 安全专家视角（权重 0.25）

#### 2.3.1 评审结论：**APPROVE with Veto Warning**（附 1 项一票否决警告）

#### 2.3.2 评审意见

**优点认可**：
- P0 安全相关用户故事优先级正确（OutputValidator / DependencyHallucinationChecker / DeploymentComplianceChecker）
- 覆盖了 OWASP Agentic Top 10 的关键威胁（ASI02 工具误用 / ASI04 供应链 / ASI09 信任利用）
- 红队测试设计完整（6 类 Prompt Injection + 路径穿越 + 审计链篡改 + RBAC fail-closed）

**否决警告 1：`DeploymentComplianceChecker` 必须前置到 Phase 0（P0，一票否决）**

原方案把 `DeploymentComplianceChecker` 放在 Wave 1 第 1.3 项，但 project_memory 教训显示：
- 2026-07-12 基础版违规部署事故已经发生
- 该事故根因是"部署前未检查硬约束"
- 如果不优先解决，可能再次发生违规部署

**要求**：`DeploymentComplianceChecker` 必须在 Phase 0 完成（即使简化版也行），作为"防违规部署兜底"。

#### 2.3.3 防幽灵功能建议

| 新模块 | 安全集成验证 | 红队测试要求 |
|--------|------------|------------|
| `DependencyHallucinationChecker` | 集成后扫描 DevSquad 自身代码，0 幻觉包 | 注入幻觉包测试用例 ≥10 条 |
| `OutputValidator` | 集成后扫描 DevSquad LLM 输出，0 敏感信息泄露 | 注入敏感信息测试用例 ≥20 条 |
| `DeploymentComplianceChecker` | 集成后扫描 DevSquad 部署目标，100% 合规 | 违规部署测试用例 ≥5 条 |
| `BenchmarkRegressionChecker` | 不涉及安全（纯性能） | 无 |

**安全角色一票否决权保留**：如果任何新模块集成后引入新的安全漏洞，安全角色有权否决该模块发布。

---

### 2.4 测试专家视角（权重 0.15）

#### 2.4.1 评审结论：**CONDITIONAL APPROVE**（附 2 项必须修改条件）

#### 2.4.2 评审意见

**优点认可**：
- E2E 验证点设计到位，每个用户故事都有可观察的验收标准
- 真实用户模拟测试设计合理（PM/开发者/运维/项目负责人 4 类角色）
- 测试维度完整性覆盖 7 维度（Happy/Error/Boundary/Performance/Configuration/Integration/Security）

**问题 1：测试场景骨架必须先于模块实现（P0，必须修改）**

用户明确要求"建立测试场景骨架是个很好的实践"。原方案 Wave 1 第 1.5 项才提"建立 E2E 测试基线"，太晚。要求：
- Phase 0 必须先建立 8 个 E2E 测试场景骨架（test stub，先 fail）
- 模块实现时逐个让骨架测试 pass（TDD 模式）
- Phase 结束时所有骨架测试必须 pass

**问题 2：新模块的测试维度未明确（P1，必须修改）**

原方案只说"4 个新模块单元测试覆盖率 ≥80%"，没说测试维度。要求每个新模块必须覆盖：
- Happy Path ≥50%（正常 import / 正常输出 / 正常部署 / 正常 benchmark）
- Error Case ≥15%（网络错误 / 无效输入 / 数据库失败 / baseline 缺失）
- Boundary ≥10%（空 import / 超长输出 / 本地部署 / baseline 边界）
- Integration ≥10%（与 dispatch pipeline 集成 / 与 SecuritySkill 集成）
- Security ≥5%（恶意 import / 注入输出 / 违规部署 / baseline 篡改）

#### 2.4.3 防幽灵功能建议

测试专家视角，"幽灵功能"= 没有测试覆盖的功能。要求：
1. 每个新模块必须有对应的 `test_<module>.py`，覆盖率 ≥80%
2. 每个新模块必须有至少 1 个 E2E 测试覆盖 Skill 调用链
3. CI 必须包含"模块被 Skill 调用次数 > 0"的检查（防止模块存在但从未被调用）

---

### 2.5 开发者视角（权重 0.10）

#### 2.5.1 评审结论：**APPROVE**（附 1 项建议）

#### 2.5.2 评审意见

**优点认可**：
- 用户故事格式标准（作为...我希望...以便...）
- 验收标准可观察可度量
- 微任务拆解到 2-5 分钟粒度，可执行性好

**建议 1：新模块实现应优先复用现有组件（P2）**

原方案 4 个新模块都是从零开始。建议优先复用：
- `DependencyHallucinationChecker`：复用 `InputValidator` 的模式匹配 + `OperationClassifier` 的三级分类
- `OutputValidator`：复用 `InputValidator` 的 53 模式检测（反向应用）
- `DeploymentComplianceChecker`：复用 `OperationClassifier` + `PermissionGuard`
- `BenchmarkRegressionChecker`：复用 `PerformanceMonitor` 的 P95/P99 逻辑

#### 2.5.3 防幽灵功能建议

开发者视角，"幽灵功能"= 写了但没人调用的代码。要求：
1. 每个新模块的 `__init__.py` 必须有 `public_api` 列表，明确导出哪些函数
2. 每个新模块必须在 `dispatcher.py` 的 `_register_skills()` 或 `_register_hooks()` 中注册
3. 每个新模块必须有"被调用次数"计数器，CI 检查 > 0

---

### 2.6 DevOps 视角（权重 0.05）

#### 2.6.1 评审结论：**APPROVE**（附 1 项建议）

#### 2.6.2 评审意见

**优点认可**：
- P10 部署阶段用户故事覆盖完整（一键部署/回滚/原子写入/合规检查）
- P11 运维阶段用户故事覆盖完整（日志根因/技术债/活文档/性能基准）

**建议 1：`BenchmarkRegressionChecker` 必须集成到 nightly CI（P1）**

原方案说"nightly CI benchmark job"，但没说具体集成方式。要求：
- nightly CI workflow 文件 `.github/workflows/nightly.yml` 必须包含 benchmark job
- benchmark 数据落盘到 `.benchmarks/v{version}_baseline.json`
- 性能回归 > 10% 时 CI 红灯 + 通知（GitHub Actions Slack notification）
- baseline 文件由 DevSquad 自动管理（发布版本时自动更新）

#### 2.6.3 防幽灵功能建议

DevOps 视角，"幽灵功能"= CI 中存在但从不运行的 job。要求：
1. 每个新模块的 CI job 必须在最近 7 天内运行过至少 1 次
2. CI job 失败必须有告警（不能静默失败）
3. nightly CI 必须包含"模块活跃度检查"（每个模块最近 30 天被调用次数 > 0）

---

### 2.7 UI 设计师视角（权重 0.05）

#### 2.7.1 评审结论：**APPROVE**（附 1 项建议）

#### 2.7.2 评审意见

**优点认可**：
- P5 交互设计阶段用户故事覆盖可用性和 a11y
- 真实用户模拟测试设计包含 PM/开发者/运维/项目负责人 4 类角色

**建议 1：新模块的"可见性"设计（P2）**

新模块（如 `DependencyHallucinationChecker`）对用户来说是"后台功能"，但需要在报告中可见：
- `devsquad run` 输出的 Markdown 报告中，新增"安全检查"章节，列出各模块触发情况
- Dashboard 增加"模块活跃度"面板，显示每个模块的调用次数和效果
- CLI 增加 `devsquad status --modules` 命令，查看各模块状态

#### 2.7.3 防幽灵功能建议

UI 视角，"幽灵功能"= 用户看不到的功能。要求：
1. 每个新模块必须在 Markdown 报告中有专属章节
2. 每个新模块必须在 Dashboard 中有可视化展示
3. 每个新模块必须有"触发日志"（用户可查看该模块何时被触发、结果如何）

---

## 三、防幽灵功能集成方案（核心）

### 3.1 幽灵功能定义与历史教训

**定义**：幽灵功能 = 代码存在但从未被 Skill 调用、从未被用户感知、从未被测试覆盖的功能。

**历史教训**：
- V3.9 之前 DevSquad 有 19 个孤立原型（~5000 行幽灵代码）
- V4.0.0 升级时强调"无幽灵功能"，每个新模块都集成到 dispatch pipeline
- project_memory 教训："subagent 在代码质量评估上严重误报，必须实际运行命令验证"

**幽灵功能三大特征**：
1. **无 Skill 调用链**：模块存在但不在 dispatch pipeline 中
2. **无测试覆盖**：模块存在但 CI 不运行
3. **无用户可见性**：模块存在但用户报告/状态中看不到

### 3.2 Skill 调用链集成矩阵（核心）

> 每个新模块必须明确：集成到哪个 Skill / 在哪个阶段触发 / 通过哪个 API 暴露 / 如何可见

| 新模块 | Skill 集成 | dispatch 阶段 | dispatcher 公共 API | 用户可见性 |
|--------|----------|-------------|-------------------|----------|
| `DependencyHallucinationChecker` | `SecuritySkill` 扩展 | P8 post-worker hook | `security_scan_dependencies(code: str) -> DependencyScanResult` | Markdown 报告"安全检查"章节 + Dashboard 模块活跃度面板 |
| `OutputValidator` | `dispatch` pipeline post-worker hook | P8 post-worker（自动触发） | dispatcher 自动调用，无需用户显式调用 | Markdown 报告"输出验证"章节 + 审计日志 |
| `DeploymentComplianceChecker` | `dispatch` lifecycle gate | P10 部署门禁 | `lifecycle_gate_check(phase="P10", target_env: str) -> ComplianceReport` | Markdown 报告"部署合规"章节 + 阻断违规部署 |
| `BenchmarkRegressionChecker` | `dispatch` lifecycle gate + nightly CI | P11 运维门禁 + nightly | `lifecycle_gate_check(phase="P11", baseline_version: str) -> BenchmarkReport` | Markdown 报告"性能基准"章节 + nightly CI 报警 |

### 3.3 集成点设计原则

**原则 1：Skill 优先，模块次之**
- 先设计"Skill 如何调用"，再设计"模块如何实现"
- 模块是 Skill 的实现细节，Skill 是用户的接口

**原则 2：dispatcher 公共 API 必须显式暴露**
- 每个新模块必须通过 dispatcher 的公共 API 暴露（参考 `dispatch_with_loop()` / `qa_audit_url()` 模式）
- 不允许"模块存在但 dispatcher 不知道"

**原则 3：lifecycle gate 是天然集成点**
- P8 实现阶段：post-worker hook（OutputValidator / DependencyHallucinationChecker）
- P10 部署阶段：lifecycle gate（DeploymentComplianceChecker）
- P11 运维阶段：lifecycle gate（BenchmarkRegressionChecker）

**原则 4：用户可见性是验收标准**
- 每个新模块必须在 Markdown 报告中有专属章节
- 每个新模块必须有"触发日志"（用户可查看）
- CI 必须检查"模块被调用次数 > 0"

### 3.4 Skill 调用链图示

```
用户任务 → [InputValidator] → [RoleMatcher] → [Coordinator]
                                              ↓
                                    [Worker 并行执行]
                                              ↓
                                    [post-worker hooks] ← 新模块集成点 1
                                      ├─ OutputValidator（自动触发）
                                      ├─ DependencyHallucinationChecker（SecuritySkill 调用）
                                      └─ 现有 hooks（slice_outputs / check_anchor_drift）
                                              ↓
                                    [ConsensusEngine]
                                              ↓
                                    [post-dispatch hooks]
                                              ↓
                                    [lifecycle gate: P10 部署] ← 新模块集成点 2
                                      └─ DeploymentComplianceChecker
                                              ↓
                                    [lifecycle gate: P11 运维] ← 新模块集成点 3
                                      └─ BenchmarkRegressionChecker
                                              ↓
                                    [ReportFormatter] → 用户可见报告
```

---

## 四、共识结论

### 4.1 投票结果

| 角色 | 权重 | 投票 | 加权得分 | 备注 |
|------|------|------|--------|------|
| 架构师 | 0.30 | CONDITIONAL APPROVE | 0.225 | 3 项必须修改条件 |
| 安全 | 0.25 | APPROVE with Veto Warning | 0.225 | 1 项一票否决警告 |
| PM | 0.20 | APPROVE | 0.20 | 2 项建议 |
| 测试 | 0.15 | CONDITIONAL APPROVE | 0.1125 | 2 项必须修改条件 |
| 开发 | 0.10 | APPROVE | 0.10 | 1 项建议 |
| DevOps | 0.05 | APPROVE | 0.05 | 1 项建议 |
| UI | 0.05 | APPROVE | 0.05 | 1 项建议 |
| **合计** | **1.00** | **6 APPROVE + 1 CONDITIONAL** | **0.9625** | **共识通过（≥0.70）** |

### 4.2 全票通过项（7/7 同意）

1. ✅ 视角转换正确（从 DevSquad 自身到用户手头项目）
2. ✅ 35 个用户故事按 11 阶段生命周期组织合理
3. ✅ 优先级权衡合理（安全 > 质量 > 效能 > 体验）
4. ✅ E2E 验证点设计到位
5. ✅ 真实用户模拟测试设计合理
6. ✅ 防幽灵功能是核心约束

### 4.3 必须修改项（6 项，纳入修订版方案）

| # | 来源角色 | 修改项 | 优先级 |
|---|---------|--------|--------|
| M1 | 架构师 | 4 个新模块必须明确 Skill 调用链集成点 | P0 |
| M2 | 架构师 | Wave 1 节奏过快，改为 Phase 0/1/2 稳扎稳打 | P0 |
| M3 | 架构师 | 增加"集成验证"环节（零回归 + 新 E2E） | P0 |
| M4 | 安全 | `DeploymentComplianceChecker` 前置到 Phase 0 | P0 |
| M5 | 测试 | 测试场景骨架必须先于模块实现（TDD） | P0 |
| M6 | 测试 | 新模块测试维度明确（7 维度覆盖） | P1 |

### 4.4 建议项（4 项，可选采纳）

| # | 来源角色 | 建议项 | 采纳状态 |
|---|---------|--------|--------|
| S1 | PM | 用户故事按"用户旅程"重组 | 采纳（作为附录） |
| S2 | PM | 真实用户模拟测试招募标准明确化 | 采纳 |
| S3 | 开发 | 新模块优先复用现有组件 | 采纳 |
| S4 | UI | 新模块的"可见性"设计 | 采纳 |

---

## 五、修订版推进方案（稳扎稳打 + 骨架先行）

### 5.1 修订原则

```
原方案：快速胜利 → Wave 1 (2-3周) → Wave 2 (2周) → Wave 3 (3-4周)
                              ↓
修订方案：骨架先行 → Phase 0 (1周) → Phase 1 (2周) → Phase 2 (2周) → Phase 3 (2周) → Phase 4 (3周)
```

**核心改变**：
1. **Phase 0 必做**：测试骨架 + DeploymentComplianceChecker 简化版（防违规部署兜底）
2. **每个 Phase 只做 1 个新模块**（稳扎稳打，不堆砌）
3. **每个 Phase 必须通过门禁**（覆盖率/CI/E2E/Skill 集成验证）
4. **模块实现前先写测试骨架**（TDD）

### 5.2 Phase 0: 测试骨架 + 防违规部署兜底（1 周）

**目标**：建立测试场景骨架 + 部署合规性检查简化版（防违规部署事故重演）

| 任务 | 文件路径 | 验证命令 | Skill 集成 |
|------|---------|---------|----------|
| 0.1 建立 8 个 E2E 测试骨架 | `tests/e2e/test_user_stories_skeleton.py` | `pytest tests/e2e/test_user_stories_skeleton.py -v` (8 个 test 全 fail) | N/A（骨架） |
| 0.2 `DeploymentComplianceChecker` 简化版 | `scripts/collaboration/deployment_compliance_checker.py` | `pytest tests/unit/test_deployment_compliance_checker.py` | `lifecycle_gate_check(phase="P10")` |
| 0.3 集成到 P10 lifecycle gate | `scripts/collaboration/unified_gate_engine.py` | `pytest tests/integration/test_p10_gate_with_compliance.py` | dispatcher 自动调用 |
| 0.4 SKILL.md + CHANGELOG 更新 | `SKILL.md` / `CHANGELOG.md` | `bash scripts/check_doc_consistency.sh` | N/A（文档） |

**Phase 0 门禁**：
- [ ] 8 个 E2E 测试骨架存在（全部 fail，等待 Phase 1-4 填充）
- [ ] `DeploymentComplianceChecker` 简化版单元测试覆盖率 ≥80%
- [ ] P10 lifecycle gate 集成测试通过（违规部署被阻断）
- [ ] 现有 CI 全绿（零回归）
- [ ] SKILL.md 模块数 +1，测试数 +N

**Phase 0 验收 E2E**：
- E2E-06: 尝试部署基础版到云服务器，DevSquad 阻断并提示"违反硬约束：基础版禁止云端部署"

---

### 5.3 Phase 1: DependencyHallucinationChecker（2 周）

**目标**：实现 AI 代码 import 真实性校验，集成到 SecuritySkill

| 任务 | 文件路径 | 验证命令 | Skill 集成 |
|------|---------|---------|----------|
| 1.1 先写测试（TDD） | `tests/unit/test_dependency_hallucination_checker.py` | `pytest tests/unit/test_dependency_hallucination_checker.py` (先 fail) | N/A（测试） |
| 1.2 实现模块（复用 InputValidator 模式） | `scripts/collaboration/dependency_hallucination_checker.py` | `pytest tests/unit/test_dependency_hallucination_checker.py` (全 pass) | `security_scan_dependencies(code)` |
| 1.3 集成到 SecuritySkill | `skills/security/handler.py` | `pytest tests/integration/test_security_skill_with_dep_check.py` | SecuritySkill 扩展 |
| 1.4 集成到 dispatch pipeline post-worker hook | `scripts/collaboration/dispatch_hooks.py` | `pytest tests/integration/test_dispatch_with_dep_check.py` | dispatcher 自动调用 |
| 1.5 让 E2E-04 骨架测试 pass | `tests/e2e/test_user_stories_skeleton.py::test_e2e_04_dependency_check` | `pytest tests/e2e/test_user_stories_skeleton.py::test_e2e_04_dependency_check` | E2E 验证 |
| 1.6 SKILL.md + CHANGELOG 更新 | `SKILL.md` / `CHANGELOG.md` | `bash scripts/check_doc_consistency.sh` | N/A（文档） |

**Phase 1 门禁**：
- [ ] 模块单元测试覆盖率 ≥80%（7 维度覆盖：Happy/Error/Boundary/Integration/Security）
- [ ] SecuritySkill 集成测试通过
- [ ] dispatch pipeline post-worker hook 集成测试通过（零回归）
- [ ] E2E-04 测试 pass（给定幻觉包 import，检测并报警）
- [ ] CI 全绿
- [ ] SKILL.md 模块数 +1，SecuritySkill 描述更新
- [ ] 模块被调用次数 > 0（CI 检查）

---

### 5.4 Phase 2: OutputValidator（2 周）

**目标**：实现 LLM 输出二次校验，集成到 dispatch pipeline post-worker hook

| 任务 | 文件路径 | 验证命令 | Skill 集成 |
|------|---------|---------|----------|
| 2.1 先写测试（TDD） | `tests/unit/test_output_validator.py` | `pytest tests/unit/test_output_validator.py` (先 fail) | N/A（测试） |
| 2.2 实现模块（复用 InputValidator 53 模式反向应用） | `scripts/collaboration/output_validator.py` | `pytest tests/unit/test_output_validator.py` (全 pass) | dispatcher 自动调用 |
| 2.3 集成到 dispatch pipeline post-worker hook | `scripts/collaboration/dispatch_hooks.py` | `pytest tests/integration/test_dispatch_with_output_validation.py` | post-worker hook |
| 2.4 让 E2E-相关骨架测试 pass | `tests/e2e/test_user_stories_skeleton.py::test_e2e_output_validation` | `pytest tests/e2e/test_user_stories_skeleton.py::test_e2e_output_validation` | E2E 验证 |
| 2.5 SKILL.md + CHANGELOG 更新 | `SKILL.md` / `CHANGELOG.md` | `bash scripts/check_doc_consistency.sh` | N/A（文档） |

**Phase 2 门禁**：
- [ ] 模块单元测试覆盖率 ≥80%（7 维度覆盖）
- [ ] dispatch pipeline 集成测试通过（零回归）
- [ ] E2E 测试 pass（含敏感信息 LLM 输出被拦截）
- [ ] CI 全绿
- [ ] SKILL.md 模块数 +1
- [ ] 模块被调用次数 > 0

---

### 5.5 Phase 3: 质量补强（2 周）

**目标**：补齐测试和文档相关用户故事（不新增模块，只增强现有）

| 任务 | 文件路径 | 验证命令 | Skill 集成 |
|------|---------|---------|----------|
| 3.1 增强 `check_async_coverage.py` | `scripts/check_async_coverage.py` | `pytest tests/unit/test_async_coverage.py` | CI 集成 |
| 3.2 增强安全红队用例库 | `tests/security/red_team.py` | `pytest tests/security/red_team.py` | SecuritySkill 集成 |
| 3.3 增强 `DispatchAuditLogger` 审计留痕 | `scripts/collaboration/dispatch_audit.py` | `pytest tests/unit/test_dispatch_audit.py` | dispatcher 自动调用 |
| 3.4 让 E2E-相关骨架测试 pass | `tests/e2e/test_user_stories_skeleton.py` | `pytest tests/e2e/test_user_stories_skeleton.py` | E2E 验证 |
| 3.5 SKILL.md + CHANGELOG 更新 | `SKILL.md` / `CHANGELOG.md` | `bash scripts/check_doc_consistency.sh` | N/A（文档） |

**Phase 3 门禁**：
- [ ] 现有模块覆盖率不下降
- [ ] 红队测试 4 类场景全部通过
- [ ] 审计链篡改测试通过
- [ ] CI 全绿
- [ ] E2E 骨架测试累计 ≥4 个 pass

---

### 5.6 Phase 4: BenchmarkRegressionChecker + 真实用户测试（3 周）

**目标**：实现性能基准回归检查 + 真实用户模拟测试

| 任务 | 文件路径 | 验证命令 | Skill 集成 |
|------|---------|---------|----------|
| 4.1 先写测试（TDD） | `tests/unit/test_benchmark_regression_checker.py` | `pytest tests/unit/test_benchmark_regression_checker.py` (先 fail) | N/A（测试） |
| 4.2 实现模块（复用 PerformanceMonitor P95/P99） | `scripts/collaboration/benchmark_regression_checker.py` | `pytest tests/unit/test_benchmark_regression_checker.py` (全 pass) | `lifecycle_gate_check(phase="P11")` |
| 4.3 集成到 P11 lifecycle gate + nightly CI | `scripts/collaboration/unified_gate_engine.py` / `.github/workflows/nightly.yml` | `pytest tests/integration/test_p11_gate_with_benchmark.py` | dispatcher + nightly CI |
| 4.4 让 E2E-08 骨架测试 pass | `tests/e2e/test_user_stories_skeleton.py::test_e2e_08_benchmark_regression` | `pytest tests/e2e/test_user_stories_skeleton.py::test_e2e_08_benchmark_regression` | E2E 验证 |
| 4.5 真实用户模拟测试（3-5 位用户） | `tests/e2e/real_user_pilot/` | 用户反馈报告 | N/A（用户测试） |
| 4.6 SKILL.md + CHANGELOG + 案例库更新 | `SKILL.md` / `CHANGELOG.md` / `docs/cases/` | `bash scripts/check_doc_consistency.sh` | N/A（文档） |

**Phase 4 门禁**：
- [ ] 模块单元测试覆盖率 ≥80%
- [ ] P11 lifecycle gate 集成测试通过
- [ ] nightly CI benchmark job 运行成功
- [ ] E2E-08 测试 pass（性能下降 20% 触发报警）
- [ ] 真实用户模拟测试完成（3-5 位用户，反馈报告）
- [ ] CI 全绿
- [ ] SKILL.md 模块数 +1
- [ ] 案例库 +3 个真实用户案例

---

## 六、Skill 调用链映射表（防幽灵功能核心交付物）

### 6.1 完整映射表

| 新模块 | Skill 集成 | dispatcher API | 触发阶段 | 用户可见性 | CI 检查 |
|--------|----------|---------------|---------|----------|---------|
| `DeploymentComplianceChecker` | lifecycle gate | `lifecycle_gate_check(phase="P10", target_env)` | P10 部署门禁 | Markdown 报告"部署合规"章节 + 阻断违规部署 | 模块调用次数 > 0 |
| `DependencyHallucinationChecker` | SecuritySkill 扩展 | `security_scan_dependencies(code)` | P8 post-worker hook | Markdown 报告"安全检查"章节 | 模块调用次数 > 0 |
| `OutputValidator` | dispatch post-worker hook | dispatcher 自动调用 | P8 post-worker（自动） | Markdown 报告"输出验证"章节 + 审计日志 | 模块调用次数 > 0 |
| `BenchmarkRegressionChecker` | lifecycle gate + nightly CI | `lifecycle_gate_check(phase="P11", baseline_version)` | P11 运维门禁 + nightly | Markdown 报告"性能基准"章节 + nightly 报警 | nightly job 7 天内运行 |

### 6.2 防幽灵功能 CI 检查清单

```yaml
# .github/workflows/anti-ghost-check.yml
name: Anti-Ghost Feature Check
on: [push, pull_request]
jobs:
  module-activation-check:
    name: 模块活跃度检查
    runs-on: ubuntu-latest
    steps:
      - name: Check module call count
        run: |
          # 每个新模块最近 30 天被调用次数 > 0
          python3 scripts/check_module_activation.py --modules \
            deployment_compliance_checker,dependency_hallucination_checker,\
            output_validator,benchmark_regression_checker
      - name: Check Skill integration
        run: |
          # 每个新模块必须在 dispatcher 公共 API 中暴露
          python3 scripts/check_skill_integration.py --modules \
            deployment_compliance_checker,dependency_hallucination_checker,\
            output_validator,benchmark_regression_checker
      - name: Check test coverage
        run: |
          # 每个新模块测试覆盖率 ≥80%
          pytest --cov=scripts/collaboration --cov-fail-under=80
```

### 6.3 用户可见性清单

每个新模块必须在以下 3 处可见：
1. **Markdown 报告**：`devsquad run` 输出包含专属章节
2. **Dashboard**：Streamlit Dashboard 显示模块活跃度
3. **CLI 状态**：`devsquad status --modules` 显示各模块状态

---

## 七、下一步行动

### 7.1 立即行动（本周内）

1. **评审通过本共识文档**：7 角色签字确认，无否决项
2. **启动 Phase 0**：
   - 建立 8 个 E2E 测试骨架（`tests/e2e/test_user_stories_skeleton.py`）
   - 实现 `DeploymentComplianceChecker` 简化版（防违规部署兜底）
3. **更新文档**：
   - `docs/ROADMAP_v4.3.0.md` 新建（基于本共识的修订版 Roadmap）
   - `docs/PRD/v4.3.0_PRD.md` 更新（增加 Skill 调用链集成要求）

### 7.2 短期行动（1-2 周内）

1. **完成 Phase 0**：8 个 E2E 骨架 + DeploymentComplianceChecker + P10 gate 集成
2. **Phase 0 验收**：所有门禁通过，CI 全绿
3. **启动 Phase 1**：DependencyHallucinationChecker TDD 开发

### 7.3 中期行动（1-2 个月内）

1. **完成 Phase 1-3**：3 个新模块 + 现有模块增强
2. **完成 Phase 4**：BenchmarkRegressionChecker + 真实用户模拟测试
3. **V4.3.0 正式版发布**：4 个新模块全部集成，8 个 E2E 测试全 pass，3-5 个真实用户案例

### 7.4 长期行动（3-6 个月）

1. **V4.4.0**：基于 V4.3.0 用户反馈，推进剩余用户故事
2. **案例库建设**：收集 10+ 个真实用户使用 DevSquad 解决项目痛点的案例
3. **生态扩展**：DevSquad Skill 商店（用户可发布/订阅自定义 Skill）

---

## 附录 A：用户旅程视角（PM 建议补充）

> 35 个用户故事按 SDLC 阶段组织是开发者视角，按用户旅程组织是用户视角。两者互补。

### 旅程 A：PM 澄清需求 → 架构评审 → 任务拆解

```
PM 输入模糊需求
  ↓
[US-P1-001] 7 角色并行评审 → 边界条件清单 + 异常场景清单
  ↓
[US-P1-002] IntentWorkflowMapper → 工作流链 + 微任务
  ↓
[US-P1-003] 优先级框架 → 优先级矩阵
  ↓
[US-P2-001] 架构评审 → 五轴评分 + 共识
  ↓
[US-P2-004] 技术选型交叉验证 → 4 维度审查
  ↓
[US-P3-002] 微任务拆解 → 2-5 分钟可执行
```

### 旅程 B：开发者写代码 → 审查 → 测试

```
开发者写代码
  ↓
[US-P8-004] AI 代码安全漏洞拦截 → OWASP Top 10 扫描
  ↓
[US-P6-002] import 真实性校验 → 幻觉包检测
  ↓
[US-P8-001] 多视角代码审查 → 五轴评分 + Critical 拦截
  ↓
[US-P8-002] Critical 强制证据 → 7 Red Flags 检测
  ↓
[US-P9-002] 异步路径补测 → 4 类异步测试
  ↓
[US-P9-001] 覆盖率门禁真执行 → CI 红灯
```

### 旅程 C：运维部署 → 监控 → 回滚

```
运维触发部署
  ↓
[US-P10-004] 部署合规性检查 → 违规阻断
  ↓
[US-P10-001] 一键部署 → 4 阶段自动化
  ↓
[US-P10-003] 原子写入 → 崩溃恢复
  ↓
[US-P11-001] 日志根因分析 → 5 分钟出报告
  ↓
[US-P11-004] 性能基准回归 → nightly 报警
  ↓
[US-P10-002] 回滚能力 → 一键回滚
```

---

## 附录 B：真实用户模拟测试招募标准（PM 建议补充）

| 维度 | 标准 |
|------|------|
| 用户画像 | 技术栈匹配（Python/前端/运维）+ 经验级别（初中高级搭配） |
| 任务真实性 | 必须用用户手头的真实项目，不用玩具示例 |
| 反馈结构化 | Net Promoter Score（NPS）+ 任务完成率 + 痛点排名 |
| 样本量 | ≥3 位真实用户（覆盖 PM/开发者/运维 3 类角色） |
| 时长 | 每位用户 30-60 分钟（含任务执行 + 反馈收集） |
| 反馈报告 | 含定量数据（NPS/完成率）+ 定性反馈（痛点/改进建议） |

---

> **文档状态**: 活文档 — 随 Phase 推进同步更新
> **共识达成**: 2026-07-25，7 角色加权投票 0.9625（≥0.70 通过），无否决项
> **下次审查**: Phase 0 完成后
> **维护者**: DevSquad 7 角色团队
