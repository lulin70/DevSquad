# DevSquad V3.8 增强 PRD (产品需求文档)

> **文档类型**: 产品需求文档 (PRD)
> **版本**: V3.8.0
> **基于版本**: DevSquad V3.7.2 (2115 tests passing, 65% 成熟度)
> **创建日期**: 2026-06-19
> **研究来源**: Superpowers、NodeGuard、RepoReviewer、Qodo PR-Agent
> **评估依据**: [V3.8_Enhancement_Evaluation_7Role.md](../planning/V3.8_Enhancement_Evaluation_7Role.md)
> **诚实声明**: 当前成熟度 65%，本 PRD 不夸大目标，V3.8 目标成熟度 72%

---

## 目录索引

1. [Executive Summary](#一executive-summary)
2. [增强矩阵](#二增强矩阵-enhancement-matrix)
3. [采纳增强详细规格](#三采纳增强详细规格)
4. [拒绝/延后增强及理由](#四拒绝延后增强及理由)
5. [迁移计划](#五迁移计划-v372--v38)
6. [成功指标](#六成功指标)

---

## 一、Executive Summary

### 1.1 V3.8 是什么

DevSquad V3.8 是基于对 4 个多 Agent 项目（Superpowers、NodeGuard、RepoReviewer、Qodo PR-Agent）的深度研究，提炼并采纳 6 项增强提案的版本。V3.8 的核心目标是**补齐"发现问题→自动修复"的闭环、强化代码审查门禁、提升 LLM 调用稳定性**，将 DevSquad 从"功能丰富但验证不足"推进到"核心闭环可信赖"。

### 1.2 研究发现摘要

| 研究项目 | 核心发现 | 对 DevSquad 的启发 |
|----------|---------|-------------------|
| **Superpowers** | 会话级技能注入 + 两阶段代码审查 + 微任务粒度是"可执行性"的关键 | DevSquad 有技能注入但缺两阶段审查和微任务约束 |
| **NodeGuard** | 严重度路由 + 自动修复闭环是"问题闭环"的核心 | DevSquad 发现问题后依赖人工/下一轮 dispatch，闭环断裂 |
| **RepoReviewer** | 确定性 vs LLM 步骤分离是"可审计性"的基础 | DevSquad 的 WorkflowStep 未区分节点类型，可审计性弱 |
| **Qodo PR-Agent** | Judge Agent + 历史学习提升共识质量 | DevSquad 的 ConsensusEngine 仅加权投票，缺去重和冲突解决 |

### 1.3 V3.8 范围

**采纳（6 项）**:
- **P0（立即采纳）**: #2 两阶段代码审查门禁、#3 严重度路由 + 自动修复闭环、#9 内容缓存 + 速率退避
- **P1（V3.8 采纳）**: #4 Judge Agent + 历史学习、#6 确定性 vs LLM 步骤分离、#7 微任务粒度

**延后（3 项，V3.9）**: #1 自动技能注入、#5 新鲜上下文子代理、#10 本地优先产物

**观望（1 项）**: #8 多宿主适配层

### 1.4 V3.8 目标成熟度

| 维度 | V3.7.2 当前 | V3.8 目标 | 提升来源 |
|------|------------|----------|---------|
| 功能完整性 | 72 | 78 | #3 自动修复闭环补齐 |
| 测试覆盖 | 65 | 70 | #6 步骤分离推动集成测试 |
| 代码质量 | 70 | 75 | #2 两阶段审查 + #7 微任务 |
| 文档准确性 | 60 | 68 | 本 PRD + 架构文档 |
| 生产就绪度 | 55 | 65 | #9 缓存退避稳定性 |
| 安全性 | 68 | 72 | #2 安全审查 + #3 安全修复闭环 |
| **综合** | **65** | **72** | — |

### 1.5 核心价值主张

V3.8 将 DevSquad 从"单次调度生成"升级为"发现问题→自动修复→回归验证"的闭环系统：

- ✅ **质量门禁强化**: 两阶段代码审查让 P8→P9 的质量门槛从"软建议"变为"硬门禁"
- ✅ **问题闭环自动化**: 严重度路由 + 自动修复让 security/tester 发现的问题自动流转到 coder 修复
- ✅ **稳定性基石**: 内容缓存 + 抖动退避降低 API 成本 60%+，避免限流雪崩
- ✅ **决策质量提升**: Judge Agent 增强共识机制，减少重复讨论和意见拉锯
- ✅ **可审计性**: 确定性/LLM 步骤分离让流程可追溯、可重现
- ✅ **可执行性**: 微任务粒度让 AI 输出从"方向"变为"可直接执行的步骤"

---

## 二、增强矩阵 (Enhancement Matrix)

| # | 提案 | 优先级 | 影响 | 工作量 | 风险 | 决策 | 来源 |
|---|------|--------|------|--------|------|------|------|
| 2 | 两阶段代码审查门禁 | P0 | 高 | 中 | 低 | ✅ 采纳 | Superpowers |
| 3 | 严重度路由 + 自动修复闭环 | P0 | 高 | 高 | 中 | ✅ 采纳 | NodeGuard |
| 9 | 内容缓存 + 速率退避 | P0 | 中 | 低 | 低 | ✅ 采纳 | NodeGuard |
| 4 | Judge Agent + 历史学习 | P1 | 中 | 中 | 中 | ✅ 采纳 | Qodo |
| 6 | 确定性 vs LLM 步骤分离 | P1 | 中 | 低 | 低 | ✅ 采纳 | RepoReviewer |
| 7 | 微任务粒度 | P1 | 中 | 中 | 中 | ✅ 采纳 | Superpowers |
| 1 | 会话级技能自动注入 | P2 | 低 | 中 | 中 | ⏳ V3.9 | Superpowers |
| 5 | 新鲜上下文子代理 | P2 | 中 | 高 | 高 | ⏳ V3.9 | Superpowers |
| 10 | 本地优先产物 | P2 | 低 | 中 | 低 | ⏳ V3.9 | RepoReviewer |
| 8 | 多宿主适配层 | P3 | 低 | 高 | 高 | ❌ 观望 | Superpowers |

### 2.1 矩阵字段说明

- **影响**: 对 DevSquad 核心价值的提升程度（高/中/低）
- **工作量**: 实施所需人天（低 ≤2d / 中 3-5d / 高 ≥6d）
- **风险**: 实施可能引入的问题（低/中/高）
- **决策**: 采纳（V3.8）/ 延后（V3.9）/ 观望（不定）

---

## 三、采纳增强详细规格

### 3.1 #2 两阶段代码审查门禁 (P0)

#### 3.1.1 功能描述

在 P8 开发实现阶段，将代码审查从单阶段拆分为两阶段：
- **阶段1 — 规范符合性检查（Spec Compliance）**: 确定性检查，验证代码是否符合 P3 技术设计的 API 规范、P7 测试计划的可测试性要求、安全编码规范（OWASP Top 10、密钥泄露检测）。秒级完成，不通过则阻断进入阶段2。
- **阶段2 — 代码质量审查（Code Quality Review）**: LLM 驱动的深度审查，检查代码可读性、设计模式、错误处理、性能热点。分钟级完成，关键问题（CRITICAL/HIGH）阻断推进到 P9。

#### 3.1.2 架构影响

- 新增 `TwoStageReviewGate` 模块，作为 `VerificationGate` 的增强层
- 复用现有 `LifecycleGate` 的差距报告机制
- 阶段1 的确定性检查复用 `InputValidator` 的检测规则
- 阶段2 的 LLM 审查通过 `EnhancedWorker`（coder 角色）执行
- 审查结果通过 `EventBus` 发布 `review.stage1.completed` / `review.stage2.completed` 事件

#### 3.1.3 新增模块

| 模块文件 | 职责 | 预估行数 |
|----------|------|---------|
| `scripts/collaboration/two_stage_review_gate.py` | 两阶段审查门禁核心逻辑 | ~300 |
| `scripts/collaboration/spec_compliance_checker.py` | 阶段1 确定性规范检查器 | ~250 |

#### 3.1.4 现有模块变更

| 模块文件 | 变更内容 |
|----------|---------|
| `verification_gate.py` | 增加 `TwoStageReviewGate` 调用入口，保持向后兼容 |
| `dispatch_steps.py` | PostDispatchPipeline 在 step9 (post_exec) 后插入两阶段审查步骤 |
| `workflow_engine.py` | `WorkflowStep` 增加 `review_stage` 字段（"spec" / "quality" / "none"） |
| `lifecycle_gate.py` | P8→P9 门禁增加两阶段审查通过条件 |

#### 3.1.5 测试计划

- **单元测试**: `TwoStageReviewGate` 的阶段1/阶段2 独立测试（~30 cases）
- **集成测试**: 两阶段审查与 dispatch 管线集成（~15 cases）
- **E2E 测试**: 模拟真实代码审查场景，验证阻断行为（~5 cases）
- **边界测试**: 阶段1 通过但阶段2 失败、阶段1 失败不进入阶段2、超时处理
- **回归测试**: 现有 `VerificationGate` 行为不变

#### 3.1.6 文档更新

- `docs/spec/SPEC.md`: 新增两阶段审查章节
- `docs/guides/QUICK_REFERENCE.md`: 新增两阶段审查配置说明
- `CHANGELOG.md`: V3.8 变更记录

---

### 3.2 #3 严重度路由 + 自动修复闭环 (P0)

#### 3.2.1 功能描述

在 security/tester 角色输出问题清单后，新增 Severity Router 进行严重度分级和路由：
- **严重度分级**: CRITICAL / HIGH / MEDIUM / LOW
- **门禁规则**: HIGH 及以上问题阻断当前阶段推进，自动触发 coder 修复子任务
- **自动修复闭环**: coder 修复 → 回归验证（tester/security 复检）→ 通过则继续推进 / 失败则重试（最多 3 轮）/ 3 轮失败则升级人工
- **V3.8 范围限制**: 仅支持"开发期自动修复"（修复走完整 CI），"生产期自动修复"延后到 V3.9

#### 3.2.2 架构影响

- 新增 `SeverityRouter` 模块，订阅 `EventBus` 的 `security.output.ready` / `tester.output.ready` 事件
- 自动修复子任务复用 `EnhancedWorker`（coder 角色）+ `Coordinator` 调度
- 修复结果通过 `EventBus` 发布 `autofix.completed` / `autofix.failed` 事件
- 回归验证复用 `PostDispatchPipeline` 的测试执行步骤
- 与 #2 两阶段审查联动：修复后的代码需重新通过阶段1 规范检查

#### 3.2.3 新增模块

| 模块文件 | 职责 | 预估行数 |
|----------|------|---------|
| `scripts/collaboration/severity_router.py` | 严重度分级 + 路由决策 | ~280 |
| `scripts/collaboration/auto_fix_loop.py` | 自动修复闭环控制（重试、升级、降级） | ~320 |
| `scripts/collaboration/issue_models.py` | Issue/Severity 数据模型 | ~120 |

#### 3.2.4 现有模块变更

| 模块文件 | 变更内容 |
|----------|---------|
| `dispatch_steps.py` | step10 (consensus) 后插入 SeverityRouter 处理步骤 |
| `event_bus.py` | 新增 `security.output.ready` / `tester.output.ready` / `autofix.*` 事件类型 |
| `coordinator.py` | 新增 `schedule_fix_subtask()` 方法用于调度修复子任务 |
| `enhanced_worker.py` | 支持接收"修复上下文"（原始问题 + 相关代码） |
| `dispatch_models.py` | `DispatchResult` 增加 `auto_fix_log` 字段 |

#### 3.2.5 测试计划

- **单元测试**: SeverityRouter 分级逻辑、AutoFixLoop 状态机（~40 cases）
- **集成测试**: security→SeverityRouter→coder→回归验证 全链路（~20 cases）
- **E2E 测试**: 模拟 HIGH 安全问题自动修复场景（~5 cases）
- **边界测试**: 修复 3 轮失败升级人工、修复引入新问题、CRITICAL 问题立即阻断
- **安全测试**: 验证修复后代码通过安全回归扫描（复用 `InputValidator`）
- **E2E 真实用户测试**（发布前必做）: 模拟真实用户提交含安全漏洞的代码，验证自动修复闭环端到端可用

#### 3.2.6 文档更新

- `docs/spec/SPEC.md`: 新增严重度路由与自动修复章节
- `docs/roles/security/SECURITY_AUDIT_TEMPLATE.md`: 增加严重度标注规范
- `docs/roles/test-expert/TEST_PLAN_TEMPLATE.md`: 增加缺陷严重度分级标准
- `CHANGELOG.md`: V3.8 变更记录

---

### 3.3 #9 内容缓存 + 速率退避 (P0)

#### 3.3.1 功能描述

强化现有 LLM 缓存和重试机制：
- **SHA-256 内容缓存**: 统一缓存键为 `sha256(prompt + system_prompt + model + temperature)`，避免键冲突。支持 L1（内存）→ L2（Redis）→ LLM 三级回源。
- **抖动指数退避**: 在现有 `LLMRetryBase` 的指数退避基础上增加抖动（jitter），公式 `delay = min(base * 2^attempt, max_delay) * (0.5 + random() * 0.5)`，避免高并发同步重试风暴。
- **缓存敏感度标记**: 缓存条目增加 `sensitivity_level` 字段，高敏感内容（含密钥/PII）不缓存或加密缓存。
- **默认开启 Redis**: 生产环境默认启用 L2 Redis 缓存（当前默认关闭），降级链路：Redis 故障 → L1 内存缓存 → 直接 LLM 调用。

#### 3.3.2 架构影响

- 强化 `LLMCacheBase` 的键生成逻辑（统一 SHA-256）
- 强化 `LLMRetryBase` 的退避算法（增加 jitter）
- `LLMCache` / `AsyncLLMCache` 增加敏感度过滤
- `RedisCache` 默认启用配置调整
- 与 `InputValidator` 联动：检测到敏感内容的 prompt 标记为高敏感

#### 3.3.3 新增模块

| 模块文件 | 职责 | 预估行数 |
|----------|------|---------|
| `scripts/collaboration/cache_key_strategy.py` | 统一 SHA-256 键生成 + 敏感度检测 | ~150 |

#### 3.3.4 现有模块变更

| 模块文件 | 变更内容 |
|----------|---------|
| `llm_cache_base.py` | `make_key()` 统一为 SHA-256，增加 `sensitivity_level` 参数 |
| `llm_retry_base.py` | 退避算法增加 jitter，新增 `jitter_factor` 配置 |
| `llm_cache.py` / `llm_cache_async.py` | 适配新的键策略和敏感度过滤 |
| `redis_cache.py` | 默认启用配置 + 降级逻辑强化 |
| `dispatcher.py` | `enable_redis_cache` 默认值从 False 改为 True（生产环境） |

#### 3.3.5 测试计划

- **单元测试**: SHA-256 键生成、jitter 退避算法、敏感度过滤（~25 cases）
- **集成测试**: L1→L2→LLM 三级回源、Redis 故障降级（~15 cases）
- **性能测试**: 缓存命中率对比（before/after）、高并发退避无风暴（~5 cases）
- **安全测试**: 高敏感内容不缓存验证、缓存内容加密验证
- **回归测试**: 现有缓存行为兼容（旧键格式自动迁移）

#### 3.3.6 文档更新

- `docs/guides/CONFIGURATION.md`: 缓存配置说明（含敏感度策略）
- `docs/PERFORMANCE_MONITORING_INTEGRATION.md`: 缓存指标说明
- `CHANGELOG.md`: V3.8 变更记录

---

### 3.4 #4 Judge Agent + 历史学习 (P1)

#### 3.4.1 功能描述

增强 `ConsensusEngine`，新增 Judge Agent 层：
- **去重（Dedup）**: 检测多个 Worker 提出的相似意见，合并为单一提案，避免重复投票
- **冲突解决（Conflict Resolution）**: 当 Worker 意见冲突时，Judge Agent 基于角色权重 + 论据质量裁决
- **置信度过滤（Confidence Filtering）**: 低置信度（<0.5）的共识结果标记为"需人工确认"，不自动通过
- **历史决策学习（History Learning）**: 从 `MemoryBridge` 加载历史决策，为相似提案提供"先例参考"。**默认关闭**，用户显式开启；开启后仅用于"建议"非"决策"；置信度阈值 ≥0.7 才采纳历史建议

#### 3.4.2 架构影响

- 新增 `JudgeAgent` 模块，作为 `ConsensusEngine` 的前置处理层
- 历史学习复用 `MemoryBridge` 的存储和检索能力
- 置信度计算复用 `ConfidenceScore` 模块
- 与 #3 联动：Judge Agent 的冲突解决可触发 SeverityRouter（当冲突涉及安全问题时）

#### 3.4.3 新增模块

| 模块文件 | 职责 | 预估行数 |
|----------|------|---------|
| `scripts/collaboration/judge_agent.py` | Judge Agent 核心（去重、冲突解决、置信度过滤） | ~350 |
| `scripts/collaboration/decision_history.py` | 历史决策存储与检索（基于 MemoryBridge） | ~200 |

#### 3.4.4 现有模块变更

| 模块文件 | 变更内容 |
|----------|---------|
| `consensus.py` | `reach_consensus()` 前插入 JudgeAgent 预处理 |
| `memory_bridge.py` | 新增 `store_decision()` / `query_similar_decisions()` 方法 |
| `confidence_score.py` | 适配 Judge Agent 的置信度计算需求 |
| `dispatch_models.py` | `ConsensusRecord` 增加 `confidence` / `dedup_info` / `history_ref` 字段 |

#### 3.4.5 测试计划

- **单元测试**: 去重算法、冲突解决策略、置信度计算（~35 cases）
- **集成测试**: JudgeAgent + ConsensusEngine + MemoryBridge 集成（~15 cases）
- **E2E 测试**: 多角色意见冲突场景的裁决（~5 cases）
- **边界测试**: 历史学习关闭/开启对比、冷启动（无历史数据）、历史数据污染检测
- **安全测试**: 历史决策数据脱敏验证

#### 3.4.6 文档更新

- `docs/spec/SPEC.md`: 新增 Judge Agent 章节
- `docs/guides/CONFIGURATION.md`: 历史学习开关配置
- `CHANGELOG.md`: V3.8 变更记录

---

### 3.5 #6 确定性 vs LLM 步骤分离 (P1)

#### 3.5.1 功能描述

在 `WorkflowEngine` 中显式标注每个 `WorkflowStep` 的节点类型：
- **`deterministic`（确定性）**: 纯逻辑节点，如规则匹配、权限检查、结果聚合。可 100% 单元测试覆盖，可独立审计，耗时固定。
- **`llm`（LLM 调用）**: 依赖 LLM 的节点，如代码审查、方案生成、共识判断。需 Mock 测试 + 真实 LLM 集成测试，耗时波动。
- **`hybrid`（混合）**: 含确定性逻辑 + LLM 调用的节点（少数）。

#### 3.5.2 架构影响

- `WorkflowStep` 增加 `node_type` 字段
- `PrometheusMetrics` 按 `node_type` 标签区分耗时指标
- 推动补齐 LLM 步骤的真实集成测试（当前为 0）
- 为 #3 SeverityRouter 的"确定性路由"提供基础（确定性节点不触发 LLM 修复）

#### 3.5.3 新增模块

无新增模块（纯字段增强）。

#### 3.5.4 现有模块变更

| 模块文件 | 变更内容 |
|----------|---------|
| `workflow_engine.py` | `WorkflowStep` 增加 `node_type: str = "hybrid"` 字段；`PHASE_TEMPLATES` 标注各阶段节点类型 |
| `dispatch_steps.py` | 各 step 方法标注 node_type |
| `prometheus_metrics.py` | dispatch_duration Histogram 增加 `node_type` label |
| `dispatch_models.py` | `DispatchResult` 暴露 `step_types` 字段供可观测性使用 |

#### 3.5.5 测试计划

- **单元测试**: node_type 字段序列化/反序列化、模板标注正确性（~15 cases）
- **集成测试**: Prometheus 指标按 node_type 分组验证（~10 cases）
- **回归测试**: 现有 WorkflowStep 序列化兼容（旧数据 node_type 默认 "hybrid"）
- **真实 LLM 集成测试**（补齐成熟度短板）: 为所有 `llm` 类型节点补真实 LLM 调用测试（OpenAI + Anthropic 各 5 cases，共 ~50 cases）

#### 3.5.6 文档更新

- `docs/spec/SPEC.md`: 新增节点类型说明
- `docs/PERFORMANCE_MONITORING_INTEGRATION.md`: node_type 指标说明
- `CHANGELOG.md`: V3.8 变更记录

---

### 3.6 #7 微任务粒度 (P1)

#### 3.6.1 功能描述

强化 `Coordinator.plan_task()` 的任务拆分能力：
- **微任务约束**: P8 开发实现阶段的任务强制拆分为 2-5 分钟微任务，每个微任务包含：精确文件路径、变更描述、验证命令
- **粒度配置**: 按生命周期阶段配置粒度——P2 架构设计不拆微任务，P8 开发实现强制微任务，P9 测试执行按测试维度拆分
- **验证命令**: 每个微任务自带可执行验证命令（如 `pytest tests/test_xxx.py -k test_yyy`），纳入 P7 测试计划统一管理
- **上限保护**: 单任务微任务数 ≤20，超过则告警并建议拆分为子任务

#### 3.6.2 架构影响

- `Coordinator.plan_task()` 增加微任务拆分逻辑
- `ExecutionPlan` / `WorkflowStep` 增加 `file_paths` / `verification_cmd` 字段
- 与 #6 联动：微任务的验证命令是确定性节点
- 与 #2 联动：微任务的验证命令可作为阶段1 规范检查的输入

#### 3.6.3 新增模块

| 模块文件 | 职责 | 预估行数 |
|----------|------|---------|
| `scripts/collaboration/microtask_planner.py` | 微任务拆分策略 + 粒度配置 | ~280 |

#### 3.6.4 现有模块变更

| 模块文件 | 变更内容 |
|----------|---------|
| `coordinator.py` | `plan_task()` 调用 MicrotaskPlanner，P8 阶段强制微任务 |
| `workflow_engine.py` | `WorkflowStep` 增加 `file_paths: list[str]` / `verification_cmd: str` 字段 |
| `lifecycle_templates.py` | 各阶段模板增加 `microtask_policy` 配置 |
| `dispatch_models.py` | `ExecutionPlan` 增加 `microtask_count` 字段 |

#### 3.6.5 测试计划

- **单元测试**: 微任务拆分算法、粒度配置、上限保护（~25 cases）
- **集成测试**: MicrotaskPlanner + Coordinator + WorkflowEngine 集成（~15 cases）
- **E2E 测试**: 真实开发任务的微任务拆分 + 验证命令执行（~5 cases）
- **边界测试**: 简单任务不拆分、复杂任务达上限、验证命令失败处理
- **E2E 真实用户测试**（发布前必做）: 模拟真实用户提交开发任务，验证微任务可执行性和验证命令有效性

#### 3.6.6 文档更新

- `docs/spec/SPEC.md`: 新增微任务粒度章节
- `docs/roles/solo-coder/DEVELOPMENT_TEMPLATE.md`: 增加微任务规范
- `docs/roles/test-expert/TEST_PLAN_TEMPLATE.md`: 增加验证命令管理规范
- `CHANGELOG.md`: V3.8 变更记录

---

## 四、拒绝/延后增强及理由

### 4.1 #1 会话级技能自动注入 (延后 V3.9)

**理由**:
- DevSquad 已有 `RoleSkillLoader` + `PromptAssembler._get_skill_injection()` 在 dispatch 时注入技能，增量价值有限
- "会话级"概念与 DevSquad 的"任务级 dispatch"模型不完全契合，需先明确"会话"语义
- 自动注入的准确率依赖 `IntentWorkflowMapper`，当前未达 ≥90% 可靠性门槛
- 安全风险：自动注入 = 自动注入 prompt 内容，需先实现 SKILL.md 签名机制

**V3.9 前置条件**: IntentWorkflowMapper 准确率 ≥90% + SKILL.md 签名机制就绪

### 4.2 #5 新鲜上下文子代理 (延后 V3.9)

**理由**:
- DevSquad 的 7 角色协作本质是"共享上下文达成共识"，全面切换到子代理模式风险高
- 当前 `ContextCompressor` 的 4 级压缩已缓解上下文膨胀
- 子代理的上下文重建成本可能抵消"新鲜上下文"收益
- 改变协作模型对用户心智冲击大

**V3.9 计划**: 在 V3.8 的 #7 微任务粒度中预留"独立微任务可选用子代理模式"接口，V3.9 在 P8 微任务场景试点

### 4.3 #10 本地优先产物 (延后 V3.9)

**理由**:
- 当前 `CheckpointManager` 已将 checkpoint 持久化到磁盘（JSON），基本需求已满足
- Markdown 人类可读报告是锦上添花，优先级低于核心闭环
- **安全前置条件**: 当前 checkpoint 明文存储含完整上下文快照（可能含密钥/PII），实施 #10 前必须解决加密问题

**V3.9 计划**: 配合 AuditLogger 从 Preview 升级为正式集成一起做，增加产物加密

### 4.4 #8 多宿主适配层 (观望/延后)

**理由**:
- DevSquad 当前用户基数不足以支撑多宿主投入
- 多宿主 = 多攻击面 + 多部署形态 + 多测试矩阵，运维和测试成本倍增
- DevSquad 核心价值在多角色协作调度，而非跨宿主移植
- 已有 CLI + REST API + MCP Server + Dashboard 四入口，宿主适配层是额外抽象

**观望条件**: Claude Code/Cursor 市场占有率显著提升 + DevSquad 用户基数增长 5x 后重新评估

---

## 五、迁移计划 (V3.7.2 → V3.8)

### 5.1 迁移原则

- **向后兼容**: 所有现有 API（`MultiAgentDispatcher.dispatch()`、CLI 命令、REST 端点）保持兼容
- **渐进式启用**: 新功能默认关闭或"建议模式"，用户显式启用后切换为"强制模式"
- **数据迁移**: 现有 checkpoint/缓存自动迁移，旧格式兼容
- **回滚预案**: 每个增强可独立开关，出问题可快速回滚

### 5.2 迁移步骤

#### 阶段1: 基础设施强化（#9, #6）

```
Step 1.1: 升级 LLMCacheBase 键策略为 SHA-256（自动迁移旧键）
Step 1.2: 升级 LLMRetryBase 退避算法增加 jitter
Step 1.3: WorkflowStep 增加 node_type 字段（默认 "hybrid" 兼容旧数据）
Step 1.4: PrometheusMetrics 增加 node_type label
Step 1.5: 回归测试验证现有功能不受影响
```

#### 阶段2: 门禁与闭环（#2, #3）

```
Step 2.1: 实现 TwoStageReviewGate（默认"建议模式"，不阻断）
Step 2.2: 实现 SeverityRouter + AutoFixLoop（默认"仅通知模式"，不自动修复）
Step 2.3: 集成到 PostDispatchPipeline
Step 2.4: 用户可配置切换为"强制模式"
Step 2.5: E2E 测试验证闭环
```

#### 阶段3: 决策与粒度（#4, #7）

```
Step 3.1: 实现 JudgeAgent（默认关闭历史学习）
Step 3.2: 实现 MicrotaskPlanner（P8 阶段启用）
Step 3.3: 集成到 ConsensusEngine 和 Coordinator
Step 3.4: E2E 测试验证
```

#### 阶段4: 集成与发布

```
Step 4.1: 全量回归测试（2115+ 现有测试 + 新增测试）
Step 4.2: 真实 LLM 集成测试（OpenAI + Anthropic）
Step 4.3: E2E 真实用户模拟测试（发布前必做）
Step 4.4: 文档更新（SPEC/CHANGELOG/GUIDE）
Step 4.5: 版本号升级到 3.8.0
```

### 5.3 配置迁移

```yaml
# V3.8 新增配置项（.devsquad.yaml）
v3_8:
  two_stage_review:
    enabled: false          # 默认关闭，用户显式启用
    mode: "advisory"        # "advisory"（建议） | "enforcing"（强制）
    stage1_timeout: 30      # 秒
    stage2_timeout: 300     # 秒

  severity_router:
    enabled: false
    auto_fix_mode: "notify" # "notify"（仅通知） | "auto_fix"（自动修复）
    max_fix_rounds: 3
    block_threshold: "HIGH" # HIGH 及以上阻断

  cache:
    redis_enabled: true     # 生产环境默认开启
    key_strategy: "sha256"
    sensitivity_filter: true

  retry:
    jitter_enabled: true
    jitter_factor: 0.5

  judge_agent:
    enabled: false
    history_learning: false # 默认关闭
    confidence_threshold: 0.7

  microtask:
    enabled: true           # P8 阶段默认启用
    phases: ["P8"]          # 启用微任务的阶段
    max_count: 20
    duration_target_min: 2  # 目标 2-5 分钟
    duration_target_max: 5

  workflow:
    node_type_labeling: true
```

### 5.4 回滚预案

| 增强 | 回滚开关 | 回滚影响 |
|------|---------|---------|
| #2 两阶段审查 | `v3_8.two_stage_review.enabled=false` | 退化为单阶段 VerificationGate |
| #3 严重度路由 | `v3_8.severity_router.enabled=false` | 退化为人工处理问题 |
| #9 缓存强化 | `v3_8.cache.key_strategy="legacy"` | 退化为旧键策略 |
| #4 Judge Agent | `v3_8.judge_agent.enabled=false` | 退化为纯加权投票 |
| #6 步骤分离 | 无需回滚（纯字段增强） | — |
| #7 微任务 | `v3_8.microtask.enabled=false` | 退化为粗粒度任务 |

---

## 六、成功指标

### 6.1 KPI 矩阵

| 维度 | 指标 | V3.7.2 基线 | V3.8 目标 | 测量方法 | 对应增强 |
|------|------|------------|----------|---------|---------|
| **质量** | 测试覆盖率 | ~51.5% | ≥60% | pytest-cov | #6 推动集成测试 |
| **质量** | 测试数量 | 2115 | ≥2400 | pytest --co | 全部 |
| **质量** | 真实 LLM 集成测试 | 0 | ≥50 | 真实 API 调用 | #6 |
| **质量** | 代码审查阻断率 | N/A | ≥15% | TwoStageReviewGate 统计 | #2 |
| **稳定性** | 缓存命中率 | N/A | ≥40% | LLMCache stats | #9 |
| **稳定性** | API 限流发生率 | N/A | ≤2% | LLMRetry stats | #9 |
| **稳定性** | 重试风暴发生 | 偶发 | 0 | 监控告警 | #9 |
| **闭环** | 自动修复成功率 | N/A | ≥60% | AutoFixLoop stats | #3 |
| **闭环** | 问题闭环时间 | 人工（小时级） | 自动（分钟级） | SeverityRouter stats | #3 |
| **决策** | 共识去重率 | N/A | ≥20% | JudgeAgent stats | #4 |
| **决策** | 低置信度拦截率 | N/A | ≥10% | JudgeAgent stats | #4 |
| **可执行** | 微任务验证命令覆盖率 | N/A | ≥80% | MicrotaskPlanner stats | #7 |
| **可审计** | node_type 标注率 | 0% | 100% | WorkflowStep 统计 | #6 |
| **成熟度** | 综合成熟度 | 65% | 72% | MATURITY_ASSESSMENT | 全部 |

### 6.2 验收标准

#### P0 增强验收
- [ ] **#2 两阶段审查**: 阶段1 确定性检查秒级完成，阶段2 LLM 审查分钟级完成，CRITICAL/HIGH 问题阻断推进
- [ ] **#3 严重度路由**: HIGH 问题自动触发修复子任务，修复后回归验证，3 轮失败升级人工
- [ ] **#9 缓存退避**: SHA-256 键统一，jitter 退避无风暴，Redis 故障降级到 L1

#### P1 增强验收
- [ ] **#4 Judge Agent**: 去重率 ≥20%，低置信度（<0.5）拦截，历史学习默认关闭可开启
- [ ] **#6 步骤分离**: 所有 WorkflowStep 标注 node_type，Prometheus 按 node_type 分组，LLM 步骤有真实集成测试
- [ ] **#7 微任务**: P8 任务拆分为 2-5 分钟微任务，含文件路径 + 验证命令，上限 20

#### 整体验收
- [ ] **测试**: ≥2400 测试通过，通过率 ≥99.5%
- [ ] **真实 LLM**: ≥50 个真实 LLM 集成测试通过（OpenAI + Anthropic）
- [ ] **E2E 真实用户测试**: 模拟真实用户使用场景的端到端测试通过（发布前必做）
- [ ] **向后兼容**: 现有 API/CLI/REST 行为不变
- [ ] **文档**: SPEC.md / CHANGELOG.md / GUIDE 更新完成
- [ ] **成熟度**: 综合成熟度评估 ≥72%

### 6.3 发布前 E2E 测试计划（用户规则要求）

依据用户规则"测试计划中补充对系统进行 e2e 的测试，要发布前一定要做模拟真实用户使用的测试"，V3.8 发布前必须完成以下 E2E 真实用户模拟测试：

| 测试场景 | 模拟用户行为 | 验证点 | 通过标准 |
|----------|------------|--------|---------|
| 场景1: 含漏洞代码提交 | 用户提交含 SQL 注入的代码 | #3 自动检测 HIGH 问题 → 触发修复 → 回归验证 | 修复闭环完成，无 P0 残留 |
| 场景2: 多角色意见冲突 | 7 角色对架构方案意见分裂 | #4 Judge Agent 去重 + 冲突解决 + 置信度过滤 | 共识达成，低置信度标记 |
| 场景3: 微任务开发 | 用户提交中等复杂度开发任务 | #7 拆分为微任务 + 验证命令执行 | 微任务可执行，验证命令通过 |
| 场景4: 两阶段审查 | 用户提交不符合 API 规范的代码 | #2 阶段1 阻断 → 阶段2 不执行 | 阶段1 失败明确，差距报告清晰 |
| 场景5: 缓存高并发 | 100 并发相同 prompt | #9 缓存命中 + 无重试风暴 | 命中率 ≥80%，无同步重试 |
| 场景6: 完整生命周期 | 用户走 P1→P11 全流程 | 所有增强协同工作 | 全流程无阻断错误 |

---

## 附录: 交叉引用

- 7 角色评估报告: [V3.8_Enhancement_Evaluation_7Role.md](../planning/V3.8_Enhancement_Evaluation_7Role.md)
- 实施计划: [V3.8_Implementation_Plan.md](../planning/V3.8_Implementation_Plan.md)
- 架构演进: [V3.8_Architecture_Evolution.md](../architecture/V3.8_Architecture_Evolution.md)
- 现有路线图: [ROADMAP_V3.7-V4.0.md](../ROADMAP_V3.7-V4.0.md)
- 成熟度评估: [MATURITY_ASSESSMENT.md](../MATURITY_ASSESSMENT.md)
- 11 阶段定义: [lifecycle_phases_definition.md](_archive/prd/lifecycle_phases_definition.md)

---

**文档结束**

> **版本**: V1.0.0
> **创建日期**: 2026-06-19
> **状态**: 待评审 → 评审通过后进入实施
> **下次更新**: 实施过程中根据实际进展调整
