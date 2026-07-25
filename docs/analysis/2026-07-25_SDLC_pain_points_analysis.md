# 软件开发生命周期痛点分析 — DevSquad 覆盖度对照清单

> **分析日期**: 2026-07-25
> **分析方法**: 培训材料痛点提取（M0-M8 讲义 + 案例库） + 网络权威调研（Stack Overflow 2025 / Google DORA 2025 / CNCF 2026 / GitClear / Cloud Security Alliance / arXiv 论文）
> **对照基准**: DevSquad V4.2.9（149+ 核心模块，7681 测试，11 阶段生命周期模型）
> **目的**: 识别 DevSquad 已解决、部分解决、未解决的痛点，为后续 Roadmap 提供数据支撑

---

## 一、痛点来源汇总

| 来源 | 痛点数量 | 覆盖领域 |
|------|---------|---------|
| 培训材料 M0-M8 讲义 | 60+ | SDLC 全流程（需求→架构→编码→审查→测试→部署→运维） |
| 培训材料案例库 | 12 | 业界安全事件 + 讲师实操案例 |
| 网络调研 - 软件开发 | 12 | AI 代码质量、Code Review、技术债、度量、文档 |
| 网络调研 - 系统开发 | 12 | 微服务、云原生、可观测性、平台工程、基础设施 |
| 网络调研 - AI 开发 | 15 | Agent 工程化、幻觉、调试、安全、多 Agent 协作 |
| **合计（去重后）** | **~80** | **覆盖 SDLC + 系统工程 + AI 工程三大领域** |

---

## 二、已解决痛点清单（30 项）

> DevSquad 有完整机制或模块直接对应，痛点已被系统性解决。

### 2.1 需求环节（5 项）

| # | 痛点 | 来源 | DevSquad 解决方案 | 模块 |
|---|------|------|------------------|------|
| 1 | PRD 文档写得慢（格式排版占一半时间） | M1 讲义 | PM 角色 + PM Methodology Skills（5 个 SKILL.md 框架：create-prd / opportunity-solution-tree / prioritization-frameworks / assumption-mapping / experiment-design） | `role_skills/product-manager/` |
| 2 | 遗漏边界条件（开发到一半才发现） | M1 讲义 | 多角色并行评审，7 角色各从自身视角补全边界（安全看异常、测试看边界、架构看扩展） | `MultiAgentDispatcher` |
| 3 | PRD 与代码脱节（PM 说"这不是我要的"） | M1 讲义 | HMAC-SHA256 审计链 + "文档先行" Meta Iron Rule + IntentWorkflowMapper 需求→工作流映射 | `dispatch_audit.py` / `intent_workflow_mapper.py` |
| 4 | 需求变更追溯难（查不到谁同意的） | M1 讲义 | CheckpointManager SHA256 完整性 + 审计链不可篡改 + 11 阶段生命周期变更管理流程 | `checkpoint_manager.py` |
| 5 | 需求→工作流映射缺失（需求拆不到可执行任务） | 网络调研 | IntentWorkflowMapper（6 种意图 × 3 语言，带门禁要求和防跳过消息） | `intent_workflow_mapper.py` |

### 2.2 架构设计（4 项）

| # | 痛点 | 来源 | DevSquad 解决方案 | 模块 |
|---|------|------|------------------|------|
| 6 | 架构师一人拍板（上线后发现安全没考虑） | M2 讲义 | 7 角色并行架构评审 + 加权共识投票（架构师 0.30 / 安全 0.25 / 架构 0.20 / 性能 0.15 / 可读性 0.10） | `FiveAxisConsensusEngine` |
| 7 | 技术选型无交叉验证（安全团队说"这不安全"→推翻重来） | M2 讲义 | 多角色视角审查：架构师看设计 + 安全专家查漏洞 + 测试员验可测性 + 运维看部署复杂度 | `MultiAgentDispatcher` |
| 8 | 架构决策无记录（6 个月后新人问"为什么这么设计"） | M2 讲义 | ADR 系统 + GLOSSARY 术语表 + 11 阶段生命周期 P2 架构设计门禁（加权共识 ≥70%） | `WorkflowEngine` / `glossary_loader.py` |
| 9 | 架构过度设计识别不足 | 网络调研 | RedesignAuditor 第三阶段简洁性审计（YAGNI / STDLIB / DUPLICATE / OVERENGINEERING 四维检测） | `redesign_auditor.py` |

### 2.3 代码审查（5 项）

| # | 痛点 | 来源 | DevSquad 解决方案 | 模块 |
|---|------|------|------------------|------|
| 10 | 代码审查走形式（"LGTM" 3 秒 approve） | M4 讲义 | FiveAxisConsensusEngine 五轴评分 + 三级分类（Critical / Important / Minor）+ 安全角色一票否决 | `five_axis_consensus.py` |
| 11 | 审查者视角单一（后端审查后端，没人从安全/测试角度看） | M4 讲义 | 7 角色并行审查，各角色有独立的 SKILL.md 方法论框架和 AntiRationalization 防借口表 | `anti_rationalization.py` |
| 12 | Critical 问题漏过（LLM 输出可能注入下游） | M4 讲义 | VerificationGate 7 Red Flags 检测 + Prove-It Pattern 强制证据 + 安全角色 Critical 否决权 | `verification_gate.py` |
| 13 | 审查无审计留痕（谁说了什么查不到） | M4 讲义 | DispatchAuditLogger HMAC-SHA256 链式哈希审计日志（length-prefixed 编码消除边界歧义） | `dispatch_audit.py` |
| 14 | AI 代码安全漏洞率高于人写代码（2.74 倍） | 网络调研 (CodeRabbit) | InputValidator 53 种注入模式检测 + OperationClassifier 三级操作分类（ALWAYS_SAFE / NEEDS_REVIEW / FORBIDDEN） | `input_validator.py` / `operation_classifier.py` |

### 2.4 测试质量（5 项）

| # | 痛点 | 来源 | DevSquad 解决方案 | 模块 |
|---|------|------|------------------|------|
| 15 | 测试写得慢（一个函数 5 个测试花 2 小时） | M5 讲义 | TestSkill 子技能 + TestQualityGuard 自动生成三组测试（正常/边界/异常） | `skills/test/` / `test_quality_guard.py` |
| 16 | 覆盖率造假（行覆盖 75% 但全是 `assert True`） | M5 讲义 | TestQualityGuard 弱断言检测（`assertTrue` / `>0.0` 阈值 / bare `except:` / magic numbers 自动标记） | `test_quality_guard.py` |
| 17 | 异步路径 0% 覆盖 | M5 讲义 | `check_async_coverage.py` 专项异步覆盖率检查 + AsyncCoordinator `return_exceptions=True` 安全模式 | `check_async_coverage.py` |
| 18 | CI 门禁形同虚设（设了 75% 但实际 70.74% 还是绿的） | M5 讲义 | 质量门禁五件套（pre-commit + ruff + mypy + coverage + radon）+ `check_dependency_lock.py` 版本锁 + `check_version_consistency.py` 一致性检查 | CI/CD pipeline |
| 19 | 安全测试缺失（无 prompt injection / 路径穿越检测） | M5 讲义 | 安全红队测试：6 类 Prompt Injection + 路径穿越 sanitize + 审计链篡改检出 + RBAC fail-closed | `InputValidator` / `security/` |

### 2.5 部署运维（6 项）

| # | 痛点 | 来源 | DevSquad 解决方案 | 模块 |
|---|------|------|------------------|------|
| 20 | 部署靠手敲（SSH 上去拉代码重启，每次 20 分钟） | M6 讲义 | CLI 6 命令生命周期快捷方式（spec/plan/build/test/review/ship）+ `start.sh` 一键启动脚本 | `cli.py` / `start.sh` |
| 21 | 回滚靠记忆（"上个版本是啥来着"） | M6 讲义 | CheckpointManager 生命周期状态持久化（save/restore/list/delete）+ GitDriver 自动 git 操作 + 风险等级评估 | `checkpoint_manager.py` / `git_driver.py` |
| 22 | 崩溃后从头来（长任务跑 2 小时崩溃没有断点） | M6 讲义 | Checkpoint 断点续传 + SHA256 完整性校验 + UnifiedMemory 持久化层（备份恢复） | `loop_engineering/unified_memory.py` |
| 23 | 日志靠 grep（SSH 上去 grep 半天找不到根因） | M7 讲义 | AI 日志根因分析 + PerformanceMonitor P95/P99 响应时间 + 瓶颈检测 + Markdown 报告 | `performance_monitor.py` |
| 24 | 技术债越积越多（每次说"下次重构"永远不来） | M7 讲义 | TechDebtManager 自动扫描 + knapsack 优先级排序 + 清理追踪 + `todo_drift_monitor` 持续监控（pre-commit + CI 集成） | `tech_debt_manager.py` / `todo_drift_monitor.py` |
| 25 | 配置散落多处（yaml / 代码 / 环境变量 / 数据库，改一个漏三个） | M6 讲义 | ConfigManager 统一配置管理（优先级：env var > ~/.yaml > ./.yaml > defaults）+ `.devsquad.yaml` 单一配置源 | `config_loader.py` |

### 2.6 文档管理（2 项）

| # | 痛点 | 来源 | DevSquad 解决方案 | 模块 |
|---|------|------|------------------|------|
| 26 | 文档与代码脱节（文档标 92% 覆盖率但实际 70.74%） | M7 讲义 | "活文档"原则 + `check_version_consistency.py` CI 自动检查（30 个位置版本一致性）+ `check_doc_consistency.sh` | CI/CD pipeline |
| 27 | 文档版本漂移（SPEC 标 V4.0.11 但项目已 V4.1.1） | M3 讲义 | `_version.py` 单一版本真相源 + SemVer 规范化 + 版本一致性 CI 阻断（不一致则 fail） | `_version.py` / CI |

### 2.7 AI 工程专项（3 项）

| # | 痛点 | 来源 | DevSquad 解决方案 | 模块 |
|---|------|------|------------------|------|
| 28 | AI 代码技术债指数级积累（churn +84%，重构 25%→<10%） | 网络调研 (GitClear) | YagniChecker 6 级 YAGNI 梯检查 + PonytailRuleInjector 7 级懒惰梯（少写多余代码）+ RedesignAuditor 过度设计检测 | `yagni_checker.py` / `ponytail_rule_injector.py` |
| 29 | Prompt Injection 攻击（CamoLeak / Rules File Backdoor） | 案例库 + 网络调研 | InputValidator 53 模式检测（14 禁止 + 21 注入 + 5 可疑）+ RuleCollector 规则注入防护 + OutputValidator 输出验证 | `input_validator.py` |
| 30 | 多 Agent 协作死锁与上下文污染 | 网络调研 (arXiv) | Scratchpad 共享黑板结构化分区 + ConsensusEngine 加权投票 + 冲突解决 + EventBus 事件驱动解耦 | `scratchpad.py` / `consensus.py` / `event_bus.py` |

---

## 三、部分解决痛点清单（18 项）

> DevSquad 有相关能力，但覆盖不完整或存在已知缺陷，需要进一步补强。

### 3.1 需求与产品（3 项）

| # | 痛点 | DevSquad 现状 | 缺口 | 建议 |
|---|------|-------------|------|------|
| 31 | AI 代写 PRD 失去用户视角（技术驱动而非用户需求驱动） | PM 角色存在 + User Story 检查 | 纯 AI 共识有盲区（7/7 APPROVE 可能反映"AI 倾向同意"而非真正批判性审查） | 引入"人类 PM 必须参与"门禁 + 共识投票至少 1 个 DISCUSS/REJECT |
| 32 | Preview 功能宣称成 Enterprise Ready | 功能成熟度有标注（Ready/Preview/Experimental） | 标注不够系统化，部分文档仍宣称 Enterprise 但含 Preview 功能 | PRD 模板增加"功能成熟度"必填列 + CI 检查文档中的成熟度声明 |
| 33 | 需求优先级判断（AI 不擅长度量真实优先级） | PM Methodology Skills 含 prioritization-frameworks | 框架存在但 AI 无法访问真实用户数据和业务价值度量 | 集成 CarryMem 用户反馈记忆 + opportunity-solution-tree 结构化优先级 |

### 3.2 架构与代码（5 项）

| # | 痛点 | DevSquad 现状 | 缺口 | 建议 |
|---|------|-------------|------|------|
| 34 | Mixin 碎片化（22 个文件服务一个类） | 已识别并通过 Mixin→Composition 重构（V3.7.2 消除 3 个 Mixin） | 历史债务未完全清除，Dispatcher 仍有多个 dispatch_*.py 文件 | 继续 Composition 重构 + CodeMapGenerator 可视化依赖关系 |
| 35 | 共识权重三处不一致 | 已统一到 `_version.py` / `models_dispatch.py` | 配置审计无持续自动化机制，可能再次漂移 | 增加 `check_config_consistency.py` 到 CI + 配置单一真相源强制检查 |
| 36 | 43 参数上帝构造器 | 已识别并在讲义中作为反面教材 | 未完全重构为嵌套配置对象（DispatcherConfig dataclass） | 按 DispatcherConfig / PathConfig / FeatureFlags / LLMConfig 分组重构 |
| 37 | OutputValidator 缺失（只查输入不查输出） | InputValidator 完善（53 模式） | LLM 输出直接存入 Scratchpad，无二次校验 | 新增 OutputValidator 模块，检测 LLM 输出中的 prompt injection / 敏感信息泄露 |
| 38 | 共识投票全投赞成 | AntiRationalizationEngine 防借口表 + FiveAxisConsensus 严格模式 | 默认 `decision=True` 问题未根治，"必提异议"机制未实现 | 每个角色至少提出 1 个潜在风险 + 随机分配 DISCUSS 角色打破一致同意 |

### 3.3 测试与质量（3 项）

| # | 痛点 | DevSquad 现状 | 缺口 | 建议 |
|---|------|-------------|------|------|
| 39 | 测试金字塔倒 T 型（96% 扁平堆在根目录） | 已改善：Contract 5.0% / Integration 15.2% / E2E 3.5% | Unit 仍占 75.9%，根目录有 176 个扁平测试文件 | 继续按子域建子目录 + 统一 `@pytest.mark.unit` marker |
| 40 | 文档数字与 CI 产物不一致 | `check_version_consistency.py` 检查版本号 | 测试数 / 覆盖率等数字仍手动维护，易过时 | CI 自动从 coverage.json / pytest --collect-only 提取数字并更新文档 |
| 41 | 版本号膨胀（1.5 个月 10+ 个版本） | SemVer 规范化 + 月度 release 尝试 | 发版频率仍较高（V4.0.0→V4.0.11 有 12 个 patch） | 严格执行"patch 只修 bug，MINOR 才加功能" + 小改进累积到 feature branch |

### 3.4 AI Agent 工程（4 项）

| # | 痛点 | DevSquad 现状 | 缺口 | 建议 |
|---|------|-------------|------|------|
| 42 | AI Agent 工程化鸿沟（85% 部署，仅 20% 系统化） | LoopKernel 五步闭环 + AutonomousLoopController | 生产监控不完整，PoC→生产缺少数据工程和反馈回路 | 增强 ProductionMonitor：prompt→completion→tool call→eval 全链路追踪 |
| 43 | LLM 幻觉问题（47% 企业基于幻觉做决策） | ConfidenceScorer 5 因子评分 | 不能根治幻觉，只能标记低置信度 | 集成 RAG + 外部知识验证 + 幻觉检测 API（Galileo Hallucination Index） |
| 44 | Agent 调试黑箱（传统 APM 无法追踪 prompt→completion） | PerformanceMonitor P95/P99 + 瓶颈检测 | 缺少 prompt→completion→tool call→eval 全链路追踪 | 新增 AgentTrace 模块，记录每次 LLM 调用的 prompt/response/tool_call/latency |
| 45 | Agent 非确定性与无法复现 | Checkpoint 断点续跑 + SHA256 完整性 | 无法保证相同输入产生相同输出（LLM 概率采样） | 记录 temperature/seed/model_version + 支持 replay 模式（回放记录的 LLM 响应） |

### 3.5 成本与效能（3 项）

| # | 痛点 | DevSquad 现状 | 缺口 | 建议 |
|---|------|-------------|------|------|
| 46 | LLM Token 成本治理 | LLMCache TTL+LRU 磁盘持久化（60-80% 成本降低）+ UsageTracker | 成本预算/告警/多租户分摊不完整 | 增加成本预算阈值 + 超额告警 + 多租户用量报表 |
| 47 | Code Review 成为新瓶颈（PR 等待时间 ×2.5） | FiveAxisConsensusEngine 并行审查 | 审查速度受 LLM 调用延迟限制，无批处理优化 | 增加异步审查队列 + 批量 PR 审查模式 + 增量审查（只审查 diff） |
| 48 | 决策疲劳（80% 工作变成决策） | AntiRationalizationEngine 减少借口 | 无判断力密度度量，无法识别决策过载 | 增加 DecisionLoad 度量 + 自动延期低优先级决策 |

---

## 四、未解决痛点清单（17 项）

> DevSquad 暂无对应能力，需要新建模块或超出 DevSquad 定位范围。

### 4.1 度量与评估（4 项）

| # | 痛点 | 来源 | 影响 | 建议 |
|---|------|------|------|------|
| 49 | METR 反直觉：资深开发者用 AI 反而变慢 19% | arXiv:2507.09089 | 组织层级 AI 编码收益被高估 | 新增 DeveloperExperience 度量：认知负荷 / 上下文切换次数 / 验证时间占比 |
| 50 | DORA 指标失灵（66% 开发者不信任） | JetBrains 2025 | 管理层基于失真数据做决策 | 设计 AI 时代新度量：验证时间 / 审查深度 / 决策质量 / 知识保留率 |
| 51 | 生产力度量回归"行数崇拜"（tokenmaxxing） | Pragmatic Engineer | 激励错位，工程师优化指标而非价值 | DevSquad 度量应关注"共识质量"而非"token 用量" |
| 52 | 实时 LLM 评测体系缺失（95% 团队缺 baseline） | FutureAGI / Maxim AI | 模型回归在用户投诉前不可见 | 新增 LLMEval 模块：延迟 / 吞吐 / 毒性 / 安全 / 满意度多维度实时监控 |

### 4.2 系统工程与云原生（5 项）

| # | 痛点 | 来源 | 影响 | 建议 |
|---|------|------|------|------|
| 53 | 微服务反向合并潮（42% 组织合并回单体） | CNCF 2025 | DevSquad 是单进程架构，不涉及微服务治理 | 超出 DevSquad 定位，建议在部署文档中提供"何时该拆/合"决策框架 |
| 54 | 可观测性缺口（51% 专家列为 Top 挑战） | Portworx 2025 | DevSquad 有 PerformanceMonitor 但非云原生可观测性 | 集成 OpenTelemetry / Prometheus / Grafana 生态 |
| 55 | 基础设施漂移（手动创建资源未编码化） | Firefly | DORA 指标全部受损 | 增加 IaC 覆盖率检查 + Terraform/Pulumi 一致性验证 |
| 56 | 平台工程初期拖累交付（throughput -8%） | DORA 2024 | IDP 投入大见效慢 | 超出 DevSquad 定位，建议提供 Platform Engineering 成熟度评估框架 |
| 57 | AI on K8s 成熟度低（仅 7% 每日部署模型） | CNCF 2026 | AI 工程化能力薄弱 | 增加 MLOps pipeline 模板（模型训练→打包→部署→监控） |

### 4.3 AI 安全专项（4 项）

| # | 痛点 | 来源 | 影响 | 建议 |
|---|------|------|------|------|
| 58 | Slopsquatting 供应链攻击（20% AI 代码引用幻觉包） | CSA 2026 | 恶意包被抢注并安装 | 新增 DependencyHallucinationChecker：校验 AI 生成代码中的 import 是否对应真实存在的 PyPI/npm 包 |
| 59 | OWASP Agentic Top 10 威胁 | OWASP 2026 | ASI02 工具误用 / ASI04 供应链 / ASI05 意外执行 / ASI09 信任利用 | 对照 OWASP Agentic Top 10 逐项审查 DevSquad 覆盖度，补全缺失项 |
| 60 | Rules File Backdoor（不可见 Unicode 隐藏恶意指令） | Pillar Security | 恶意代码静默传播 | 增加 RulesFileScanner：检测 .cursor/rules / .devsquad.yaml 中的不可见 Unicode 字符 |
| 61 | AI 工具供应链安全（Amazon Q / Cursor / Copilot 被植入） | 案例库 | AI 工具自身成为攻击目标 | 增加 ThirdPartyToolAuditor：审计 DevSquad 依赖的 AI 工具链安全性 |

### 4.4 RAG 与数据（2 项）

| # | 痛点 | 来源 | 影响 | 建议 |
|---|------|------|------|------|
| 62 | RAG 数据访问控制（文档级权限管理） | TechTarget | 合规风险高 | MemoryBridge 增加文档级 ACL + 向量库加密 |
| 63 | RAG 幻觉率超 10%（法律/医疗域超 20%） | Galileo Hallucination Index | 企业 AI 可信度受损 | 集成幻觉检测 API + 知识图谱验证 + 引用溯源 |

### 4.5 团队与组织（2 项）

| # | 痛点 | 来源 | 影响 | 建议 |
|---|------|------|------|------|
| 64 | 开发者满意度历史性低位（仅 25% 满意） | Stack Overflow 2025 | 人员流动加剧，知识流失 | 超出 DevSquad 定位，建议在 PM 角色中增加 TeamHealth 度量 |
| 65 | 上流瓶颈暴露（下游快了，上游 PM 没变） | Qiita | PM/技术 lead 成为新瓶颈 | DevSquad PM 角色增强：AI 辅助需求澄清 + 跨团队对齐 + 决策加速 |

---

## 五、优先级矩阵

### 5.1 按"影响 × 紧急度"排序的 Top 10 待解决痛点

| 排名 | 痛点 | 影响 | 紧急度 | 解决难度 | 建议优先级 |
|------|------|------|--------|---------|-----------|
| 1 | #37 OutputValidator 缺失（LLM 输出无二次校验） | P0 安全 | 高 | 中 | **V4.3.x P0** |
| 2 | #58 Slopsquatting 供应链攻击 | P0 安全 | 高 | 低 | **V4.3.x P0** |
| 3 | #44 Agent 调试黑箱（无全链路追踪） | P0 效能 | 高 | 高 | **V4.4.x P1** |
| 4 | #42 AI Agent 工程化鸿沟（生产监控不完整） | P0 效能 | 高 | 高 | **V4.4.x P1** |
| 5 | #38 共识投票全投赞成（共识形同虚设） | P1 质量 | 中 | 低 | **V4.3.x P1** |
| 6 | #34 Mixin 碎片化历史债务 | P1 可维护性 | 中 | 中 | **V4.4.x P1** |
| 7 | #36 43 参数上帝构造器 | P1 可维护性 | 中 | 中 | **V4.4.x P1** |
| 8 | #40 文档数字与 CI 产物不一致 | P1 文档 | 中 | 低 | **V4.3.x P1** |
| 9 | #46 LLM Token 成本治理不完整 | P1 成本 | 中 | 中 | **V4.4.x P2** |
| 10 | #59 OWASP Agentic Top 10 覆盖不全 | P0 安全 | 高 | 高 | **V4.4.x P0** |

### 5.2 按 SDLC 阶段统计覆盖度

| SDLC 阶段 | 已解决 | 部分解决 | 未解决 | 覆盖率 |
|-----------|--------|---------|--------|--------|
| 需求分析 | 5 | 3 | 1 | 56% |
| 架构设计 | 4 | 2 | 0 | 67% |
| 编码实现 | 0 | 3 | 0 | 0% → 50%（部分） |
| 代码审查 | 5 | 1 | 0 | 83% |
| 测试质量 | 5 | 2 | 1 | 63% |
| 部署运维 | 6 | 0 | 3 | 67% |
| 文档管理 | 2 | 1 | 0 | 67% |
| AI 工程专项 | 3 | 4 | 7 | 21% |
| 系统工程 | 0 | 0 | 5 | 0%（超出定位） |
| 度量评估 | 0 | 2 | 4 | 0% → 25%（部分） |

### 5.3 关键发现

1. **DevSquad 在 SDLC 核心环节（需求→审查→测试→部署）覆盖率高（50-83%）**，这些是 DevSquad 的核心价值区域
2. **AI 工程专项覆盖率最低（21%）**，Agent 调试/监控/评测/安全是最大短板，也是业界 2025-2026 年最关注的领域
3. **系统工程与云原生覆盖率为 0%**，这超出 DevSquad 的定位（DevSquad 是开发时工具，不是运行时基础设施）
4. **度量评估覆盖率为 0-25%**，DORA 失灵和 AI 时代新度量是业界新议题，DevSquad 有机会定义"AI 协作度量"新标准
5. **安全相关痛点贯穿所有阶段**，从 Prompt Injection 到 Slopsquatting 到 OWASP Agentic，需要系统性安全加固

---

## 六、建议的 Roadmap 方向

### V4.3.x（近期 — 安全加固 + 质量补强）

- **P0**: OutputValidator 模块（LLM 输出二次校验）
- **P0**: DependencyHallucinationChecker（AI 代码 import 真实性校验）
- **P0**: RulesFileScanner（不可见 Unicode 检测）
- **P1**: 共识"必提异议"机制（打破全投赞成）
- **P1**: 文档数字 CI 自动化（从 coverage.json 提取）
- **P1**: 配置一致性 CI 检查（`check_config_consistency.py`）

### V4.4.x（中期 — AI 工程化补强）

- **P1**: AgentTrace 全链路追踪（prompt→completion→tool call→eval）
- **P1**: DispatcherConfig 嵌套配置重构（消除 43 参数）
- **P1**: Mixin 历史债务清理（Composition 完成）
- **P2**: LLM 成本预算与告警
- **P2**: LLMEval 实时评测体系

### V4.5.x+（远期 — 新领域探索）

- **P0**: OWASP Agentic Top 10 逐项覆盖
- **P1**: AI 时代新度量体系（验证时间 / 审查深度 / 决策质量 / 知识保留率）
- **P2**: RAG 幻觉检测与引用溯源
- **P2**: MLOps pipeline 模板

---

## 附录：数据来源

### 培训材料
- `/Users/lin/WorkBuddy/2026-07-18-23-08-30/training-materials/lecture-notes/M0-M8`（8 个模块讲义）
- `/Users/lin/WorkBuddy/2026-07-18-23-08-30/training-materials/case-library.md`（案例库）
- `/Users/lin/WorkBuddy/2026-07-18-23-08-30/training-materials/outline/training-outline-v2.0.md`（培训大纲）

### 网络调研权威来源
- Stack Overflow 2025 Developer Survey: https://survey.stackoverflow.co/2025/
- Google DORA 2025 Report: https://dora.dev/research/2025/dora-report
- CNCF Annual Cloud Native Survey 2026: https://www.cncf.io/wp-content/uploads/2026/01/CNCF_Annual_Survey_Report_final.pdf
- JetBrains State of Developer Ecosystem 2025: https://blog.jetbrains.com/research/2025/10/state-of-developer-ecosystem-2025/
- GitClear AI Code Quality Research: https://www.gitclear.com/ai_assistant_code_quality_2025_research
- Cloud Security Alliance AI Safety Report 2026: https://labs.cloudsecurityalliance.org/
- OWASP Agentic Top 10 for 2026: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026
- arXiv:2503.04596 (LLM Applications): https://arxiv.org/abs/2503.04596
- arXiv:2503.06745 (Agentic Observability): https://www.arxiv.org/pdf/2503.06745
- arXiv:2507.09089 (METR RCT): https://arxiv.org/abs/2507.09089
- LinearB 2026 Software Engineering Benchmarks: https://linearb.io/resources/software-engineering-benchmarks-report
- Galileo Hallucination Index: https://www.galileo.ai/hallucination-index

### DevSquad 内部
- SKILL.md V4.2.9（149+ 核心模块清单）
- CHANGELOG.md V4.2.9（测试金字塔 7681 tests）
- docs/prd/V4.3.0_PRD.md / docs/architecture/V4.3.0_ARCHITECTURE.md / docs/testing/V4.3.0_TEST_PLAN.md

---

> **文档状态**: 活文档 — 随 DevSquad 版本演进同步更新
> **下次审查**: V4.3.0 发布时
> **维护者**: DevSquad 架构师角色
