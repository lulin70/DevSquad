# PRD：DevSquad Protocol 接口体系与性能优化

> **文档类型**：产品需求文档 (PRD)
> 
> **版本**：v1.1
> 
> **创建日期**：2026-05-01
> 
> **负责人**：Product Manager
> 
> **状态**：已评审

---

## 更新履历

| 版本 | 日期 | 更新人 | 更新内容 | 审核状态 |
|------|------|--------|----------|----------|
| v1.0 | 2026-05-01 | PM | 初始版本 | 已评审 |
| v1.1 | 2026-05-01 | PM | 采纳评审意见：调整优先级、增加迁移指南、调整里程碑时间 | 待快速评审 |

---

## 一、需求背景

### 1.1 问题陈述

基于 CarryMem 集成启发分析（`docs/analysis/carrymem_integration_insights.md`），DevSquad v3.4 存在以下核心问题：

1. **架构耦合度高**：模块间通过具体类依赖，缺少抽象接口，导致：
   - 模块替换成本高
   - 测试困难（无法 mock）
   - 无降级机制（某模块故障影响全局）

2. **性能瓶颈**：多 Agent 间传递完整历史，导致：
   - Token 消耗呈乘法级增长（N×M）
   - 响应延迟随 Agent 数量线性增加
   - 大规模任务易 OOM

3. **可靠性不足**：Agent 输出无置信度标记，导致：
   - 错误信息连锁传播
   - 下游 Agent 无法判断上游结果可靠性
   - 缺少自动熔断机制

### 1.2 业务价值

**短期价值**（1-2 月）：
- Token 消耗减少 70-80%，降低 API 成本
- 响应速度提升 20-30%，改善用户体验
- 测试速度提升 5x，加快开发迭代

**中期价值**（3-6 月）：
- 系统可用性达 99.9%，支持生产环境部署
- 模块替换成本降低 80%，提升可维护性
- 支持 CarryMem 等外部系统集成，扩展生态

**长期价值**（6+ 月）：
- 从 demo 级框架升级为企业级编排系统
- 支持规则市场、多 Provider 等高级功能
- 建立行业标准接口，吸引第三方集成

### 1.3 目标用户

1. **DevSquad 核心开发者**：需要更灵活的架构支持新功能开发
2. **DevSquad 使用者**：需要更高性能和可靠性的多 Agent 系统
3. **第三方集成者**：需要标准接口对接 DevSquad（如 CarryMem）

---

## 二、需求范围

### 2.1 核心需求（Must Have）

#### R1：Protocol 接口体系

**需求描述**：为核心模块定义抽象接口，支持多种实现。

**验收标准**：
- ✅ 定义 `CacheProvider`、`RetryProvider`、`MonitorProvider`、`MemoryProvider` 四个 Protocol
- ✅ 每个 Protocol 包含 `is_available()` 方法，支持降级检测
- ✅ 现有模块（LLMCache、LLMRetry、PerformanceMonitor）实现对应 Protocol
- ✅ 提供 Null 实现（NullCacheProvider 等），用于降级和测试

**优先级**：P0（最高）

---

#### R2：AgentBriefing 压缩状态传递

**需求描述**：Agent 间传递压缩状态而非完整历史，减少 token 消耗。

**验收标准**：
- ✅ 定义 `AgentBriefing` 数据结构，包含：
  - task_summary（1-2 句话）
  - key_decisions（最多 5 条）
  - pending_items（待处理事项）
  - rules_applied（应用的规则 ID）
  - result_summary（执行结果摘要）
  - **confidence（置信度 0-1）** ← 与 R3 同步开发
- ✅ Agent 基类增加 `compress_to_briefing()` 方法
- ✅ Agent 基类增加 `receive_briefing()` 方法
- ✅ 编排器支持 briefing 模式（兼容完整历史模式）
- ✅ Token 消耗减少 70%+（通过性能测试验证）

**优先级**：P0（最高）

---

#### R3：置信度系统（与 R2 同步开发）

**需求描述**：Agent 输出增加置信度标记，防止错误连锁传播。

**验收标准**：
- ✅ `AgentResult` 增加以下字段：
  - confidence（0-1）
  - assumptions（假设列表）
  - warnings（警告列表）
- ✅ Agent 基类实现 `_calculate_confidence()` 方法
- ✅ 编排器在传递 briefing 时检查置信度
- ✅ 置信度 < 0.7 时自动生成警告
- ✅ 置信度 < 0.5 时暂停流程，等待人工介入

**优先级**：P0（最高）← **已从 P1 调整为 P0，与 R2 同步开发**

---

### 2.2 重要需求（Should Have）

#### R4：Null Providers 降级机制

**需求描述**：当某个模块不可用时，自动降级到 Null 实现。

**验收标准**：
- ✅ 所有 Null Provider 的 `is_available()` 返回 False
- ✅ Null Provider 的方法调用不抛异常，静默成功
- ✅ Agent 初始化时，未传入的 Provider 自动使用 Null 实现
- ✅ 系统在所有 Provider 不可用时仍能正常运行

**优先级**：P1（高）

---

#### R5：性能监控与对比

**需求描述**：提供性能对比工具，验证优化效果。

**验收标准**：
- ✅ 提供性能测试脚本，对比优化前后：
  - Token 消耗
  - 响应延迟
  - 内存占用
- ✅ 生成性能对比报告（Markdown 格式）
- ✅ 在 CI 中集成性能回归测试

**优先级**：P1（高）

---

### 2.3 期望需求（Nice to Have）

#### R6：CarryMem 适配器

**需求描述**：支持外接 CarryMem 个人化规则引擎。

**验收标准**：
- ✅ 定义 `MemoryProvider` Protocol
- ✅ 实现 `CarryMemAdapter`
- ✅ Agent 支持可选的 `memory` 参数
- ✅ 规则自动注入到 system prompt
- ✅ 提供集成示例

**优先级**：P2（中）

**依赖**：需要 CarryMem 提供 API

---

#### R7：多角色代码走读

**需求描述**：从架构师、测试专家、独立开发者三个角度进行代码走读。

**验收标准**：
- ✅ 生成架构走读报告（架构合理性、扩展性）
- ✅ 生成测试走读报告（测试覆盖率、测试质量）
- ✅ 生成代码走读报告（代码质量、可维护性）

**优先级**：P2（中）

---

## 三、非功能需求

### 3.1 性能要求

| 指标 | 当前值 | 目标值 | 验证方式 |
|------|--------|--------|----------|
| Token 消耗（3 Agent 场景） | ~25K | ≤ 6K | 性能测试 |
| 响应延迟（3 Agent 场景） | ~15s | ≤ 10s | 性能测试 |
| 测试执行时间 | ~60s | ≤ 12s | CI 统计 |
| 系统可用性 | ~95% | ≥ 99.9% | 降级测试 |

### 3.2 兼容性要求

- ✅ **向后兼容**：现有代码无需修改即可运行
- ✅ **渐进式迁移**：支持完整历史和 briefing 两种模式并存
- ✅ **Python 版本**：支持 Python 3.9+

### 3.3 测试要求

- ✅ **单元测试覆盖率**：≥ 90%
- ✅ **集成测试**：覆盖所有 Protocol 实现
- ✅ **性能测试**：验证 token 消耗和响应延迟
- ✅ **降级测试**：验证 Null Provider 降级逻辑

### 3.4 文档要求

- ✅ **架构文档**：更新架构设计文档，说明 Protocol 体系
- ✅ **API 文档**：为所有 Protocol 和 Briefing 提供 API 文档
- ✅ **迁移指南**：提供从 v3.4 迁移到 v3.5 的指南
- ✅ **性能报告**：提供优化前后的性能对比报告
- ✅ **README 更新**：更新主 README，说明新特性

---

## 四、用户故事

### US1：作为开发者，我希望能轻松替换缓存实现

**场景**：
```python
# 当前：紧耦合，难以替换
from scripts.collaboration import LLMCache
cache = LLMCache()  # 只能用这个实现

# 期望：松耦合，易于替换
from scripts.collaboration import CacheProvider, LLMCache, RedisCache
cache: CacheProvider = LLMCache()  # 或 RedisCache()
```

**验收**：
- 可以通过配置文件切换缓存实现
- 不需要修改业务代码

---

### US2：作为使用者，我希望大规模任务不会 OOM

**场景**：
- 当前：10 个 Agent 串行执行，token 消耗 100K+，易 OOM
- 期望：10 个 Agent 串行执行，token 消耗 ≤ 20K，稳定运行

**验收**：
- 通过 briefing 模式，token 消耗减少 70%+
- 内存占用稳定，不随 Agent 数量线性增长

---

### US3：作为开发者，我希望测试时不依赖真实服务

**场景**：
```python
# 当前：测试依赖真实 LLM API，慢且不稳定
def test_agent():
    agent = DevSquadAgent(cache=LLMCache())  # 需要真实缓存
    result = agent.execute(task)

# 期望：测试使用 Null Provider，快速且稳定
def test_agent():
    agent = DevSquadAgent(cache=NullCacheProvider())  # Mock 实现
    result = agent.execute(task)
```

**验收**：
- 测试速度提升 5x
务

---

### US4：作为使用者，我希望系统能自动识别不可靠的结果

**场景**：
- 当前：Agent A 输出错误结果，Agent B 基于错误结果继续执行，导致连锁错误
- 期望：Agent A 输出低置信度结果，系统自动警告 Agent B，或暂停流程

**验收**：
- 置信度 < 0.7 时，下游 Agent 收到警告
- 置信度 < 0.5 时，流程自动暂停

---

## 五、技术约束

### 5.1 架构约束

- ✅ 使用 Python Protocol（typing.Protocol）定义接口
- ✅ 不引入新的外部依赖（除 typing_extensions for Python 3.9）
- ✅ 保持与 v3.4 的向后兼容

### 5.2 性能约束

- ✅ briefing 序列化/反序列化开销 < 10ms
- ✅ 置信度计算开销 < 5ms
- ✅ Null Provider 调用开销 < 1ms

### 5.3 安全约束

- ✅ briefing 中不包含敏感信息（API key、密码等）
- ✅ 置信度计算不依赖外部服务
- ✅ Null Provider 不记录日志（避免泄露）

---

## 六、里程碑与交付物

### Milestone 0：技术预研（Week 1）← **新增**

**交付物**：
- [ ] Python Protocol 性能测试报告
- [ ] AgentBriefing 序列化性能测试
- [ ] 置信度计算准确性验证
- [ ] v3.4 性能基准测试报告

**验收标准**：
- Protocol 调用开销 < 5%
- 序列化开销 < 10ms
- 基准测试数据完整

---

### Milestone 1：Protocol 接口体系（Week 2-4）← **从 2 周调整为 3 周**

**交付物**：
- [ ] `scripts/collaboration/protocols.py`
- [ ] `scripts/collaboration/null_providers.py`
- [ ] 更新 `llm_cache.py`、`llm_retry.py`、`performance_monitor.py`
- [ ] 单元测试（覆盖率 ≥ 90%）
- [ ] API 文档
- [ ] Protocol 接口规范文档（已完成：`docs/architecture/protocol_interfaces_spec.md`）

**验收标准**：
- 所有现有模块实现对应 Protocol
- Null Provider 通过降级测试
- 向后兼容测试通过

---

### Milestone 2：AgentBriefing 与置信度系统（Week 5-7）← **R2 和 R3 合并，同步开发**

**交付物**：
- [ ] `scripts/collaboration/agent_briefing.py`
- [ ] AgentBriefing 序列化规范文档（已完成：`docs/architecture/agent_briefing_spec.md`）
- [ ] 更新 Agent 基类（compress/receive 方法）
- [ ] 更新 `AgentResult`（增加 confidence、assumptions、warnings 字段）
- [ ] 实现置信度计算逻辑
- [ ] 更新编排器（支持 briefing 模式 + 置信度检查）
- [ ] 性能测试脚本
- [ ] 性能对比报告

**验收标准**：
- Token 消耗减少 70%+
- 响应延迟减少 20%+
- 低置信度警告机制生效
- 极低置信度自动暂停
- 兼容模式测试通过

---

### Milestone 3：测试与文档（Week 8-10）

**交付物**：
- [ ] 回归测试策略文档（已完成：`docs/testing/regression_test_strategy.md`）
- [ ] 回归测试套件实现
- [ ] 性能回归测试
- [ ] **渐进式迁移指南**（`docs/MIGRATION_GUIDE_v3.5.md`）← **新增**
  - 保守路径：只用 Protocol，不用 Briefing
  - 平衡路径：Protocol + Briefing（兼容模式）
  - 激进路径：完全切换到 Briefing
- [ ] 性能优化案例（`docs/CASE_STUDY_v3.5.md`）← **新增**
- [ ] 多角色代码走读报告
- [ ] README 更新
- [ ] CHANGELOG 更新

**验收标准**：
- 所有回归测试通过
- 测试覆盖率 ≥ 92%
- 性能指标达标
- 迁移指南清晰易懂
- 代码走读通过

---

### Milestone 4：发布（Week 11）

**交付物**：
- [ ] v3.5 发布
- [ ] 发布公告
- [ ] 社区反馈收集

**验收标准**：
- 所有测试通过
- 文档完整
- 无 P0/P1 缺陷

---

## 七、风险与依赖

### 7.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 重构破坏现有功能 | 高 | 中 | 完整回归测试；渐进式迁移 |
| 性能优化效果不达预期 | 中 | 低 | 先做基准测试；分阶段验证 |
| 置信度计算不准确 | 中 | 中 | 基于历史数据调优；人工校准 |

### 7.2 资源依赖

- **开发资源**：2 名全职开发者，10 周
- **测试资源**：1 名测试工程师，4 周
- **文档资源**：1 名技术写作，2 周

### 7.3 外部依赖

- **CarryMem API**（可选）：如需实现 R6，需要 CarryMem 提供 HTTP API 或 Python SDK

---

## 八、成功指标

### 8.1 定量指标

| 指标 | 基线（v3.4） | 目标（v3.5） | 测量方式 |
|------|-------------|-------------|----------|
| Token | 25K | ≤ 6K | 性能测试 |
| 响应延迟 | 15s | ≤ 10s | 性能测试 |
| 测试速度 | 60s | ≤ 12s | CI 统计 |
| 系统可用性 | 95% | ≥ 99.9% | 降级测试 |
| 测试覆盖率 | 92% | ≥ 95% | Coverage 报告 |

### 8.2 定性指标

- ✅ 开发者反馈：架构更灵活，易于扩展
- ✅ 使用者反馈：性能提升明显，体验更好
- ✅ 代码走读：架构合理，代码质量高

---

## 九、附录

### 9.1 参考文档

1. CarryMem 集成启发分析：`docs/analysis/carrymem_integration_insights.md`
2. DevSquad v3.4 优化指南：`docs/OPTIMIZATION_GUIDE.md`
3. 上下文工程最佳实践：Anthropic Context Engineering Research

### 9.2 术语表

- **Protocol**：Python 的结构化类型（Structural Typing），定义接口规范
- **Briefing**：Agent 间传递的压缩状态，包含任务摘要和关键决策
- **Confidence**：Agent 对输出结果的置信度（0-1）
- **Null Provider**：空实现，用于降级和测试

---

**PRD 状态**：✅ 待评审

**下一步**：提交给架构师、测试专家、独立开发者评审，达成共识后进入架构设计阶段。
