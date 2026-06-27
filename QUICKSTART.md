# DevSquad 30 秒入门指南

<p align="center">
  <strong>把「单个 AI 助手」升级成「7 人 AI 专业团队」</strong>
  <br>
  <em>V3.7.2 Enterprise Ready | One task → Multi-role AI → One conclusion</em>
</p>

---

## 🎯 我是谁？

**DevSquad** 是一个多角色 AI 任务编排器。当你提交一个任务时，它不再是单个 AI 回答，而是让 **7 个专业角色**（架构师、安全专家、测试员、开发者等）**并行协作**，最后给出经过多方审核的结论。

### 核心价值（3 秒理解）

```
传统 AI:  你 ──→ ChatGPT ──→ 一个回答（可能不全面）
DevSquad:  你 ──→ DevSquad ──→ [架构师+安全+测试+开发...] ──→ 多维度共识结论
```

---

## ❓ 解决什么痛点？

| 痛点 | 传统单 AI | DevSquad |
|------|----------|----------|
| **视角单一** | 只有通用视角 | 7 个专业角色并行审视 |
| **质量不可控** | 可能遗漏安全/性能问题 | 多维度交叉验证 + 共识机制 |
| **无审计追踪** | 不知道回答依据什么 | 完整审计链 + SHA256 完整性校验 |
| **复杂任务崩溃** | 长任务容易丢失上下文 | Checkpoint 断点续传 + 工作流引擎 |

---

## ⚡ 最快怎么用？（5 分钟上手）

### 方式 1：命令行（推荐）

```bash
# 安装
pip install devsquad

# 运行 - 让 AI 团队帮你设计认证系统
devsquad run "设计一个安全的用户认证系统" --roles architect,security,tester,coder

# 输出结构化报告：
# ✅ 架构师建议：采用 JWT + Refresh Token 双 token 方案...
# ✅ 安全专家审查：需防范 CSRF、XSS、SQL 注入...
# ✅ 测试策略：单元测试覆盖率达 90%+，包含边界场景...
# ✅ 开发实现：提供完整代码框架...
# 📊 共识结论：方案可行，风险可控，建议优先实现 P0 功能...
```

### 方式 2：Python API

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

dispatcher = MultiAgentDispatcher()
result = dispatcher.dispatch(
    task="优化数据库查询性能",
    roles=["architect", "security", "tester"],  # 选择需要的角色
)

print(result.report)  # 结构化报告
print(result.consensus)  # 共识结论
```

### 方式 3：REST API

```bash
# 启动服务
devsquad server --port 8000

# 调用 API
curl -X POST http://localhost:8000/api/v1/dispatch \
  -H "Content-Type: application/json" \
  -d '{"task": "设计 API 网关", "roles": ["architect", "devops"]}'
```

---

## 👥 7 个核心角色

| 角色 | 代号 | 专长 | 典型输出 |
|------|------|------|---------|
| 🏗️ **架构师** | `architect` | 系统设计、技术选型 | 架构图、模块划分、设计模式 |
| 📋 **项目经理** | `pm` | 需求分析、进度规划 | WBS 分解、里程碑、风险评估 |
| 🛡️ **安全专家** | `security` | 安全审计、威胁建模 | 漏洞清单、安全策略、合规检查 |
| 🧪 **测试员** | `tester` | 测试策略、质量保障 | 测试计划、用例设计、覆盖率目标 |
| 💻 **开发者** | `coder` | 代码实现、技术细节 | 代码框架、API 设计、数据模型 |
| 🔧 **运维工程师** | `devops` | 部署运维、监控告警 | Dockerfile、CI/CD、监控方案 |
| 🎨 **UI 设计师** | `ui` | 用户体验、界面设计 | 原型图、交互流程、设计规范 |

---

## 🎭 使用场景示例

### 场景 1：代码审查（最常用）

```bash
# 单 AI：只给一般性建议
devsquad run "审查这段代码的安全性" --roles security

# DevSquad：多维度审查
devsquad run "审查 src/auth.py 的安全性" --roles architect,security,tester
```

**输出示例：**
```
🔍 Security Review (安全专家):
- 发现 SQL 注入风险 (Line 45)
- 密码明文存储 (Line 23)
- 建议: 使用参数化查询 + bcrypt 哈希

🏗️ Architecture Review (架构师):
- 模块耦合度过高
- 建议: 引入 Repository Pattern

🧪 Testing Review (测试员):
- 缺少异常路径测试
- 建议: 增加 mock 外部依赖的用例

📊 Consensus (共识):
✅ 通过 (3/3) — 需修复 P0 问题后合并
```

### 场景 2：技术方案评审

```bash
devsquad run "评估微服务 vs 单体架构的优劣" \
  --roles architect,pm,devops \
  --mode consensus  # 强制要求达成共识
```

### 场景 3：全生命周期管理

```bash
# CLI 6 大生命周期命令
devsquad spec "用户认证系统需求"
devsquad plan "技术选型和架构设计"
devsquad build "核心功能实现"
devsquad test "单元测试和集成测试"
devsquad review "代码审查和质量门禁"
devsquad ship "部署和发布检查"
```

---

## 🚀 进阶功能一览

### 五大能力域（按需了解）

#### 🏗️ 1. 任务编排引擎（核心）
- **Coordinator**: 自动拆解任务 + 智能分配角色
- **Scratchpad**: 角色间实时共享信息（像白板一样）
- **ConsensusEngine**: 多角色投票机制 + 冲突解决
- **BatchScheduler**: 并行/串行混合调度

#### 🛡️ 2. 质量保障体系
- **InputValidator**: 40 种检测模式（14 危险模式 + 21 Prompt 注入 + 5 可疑模式），含多语言防绕过
- **VerificationGate**: 强制要求提供证据（防止 AI 敷衍）
- **AntiRationalizationEngine**: 防止 AI 找借口
- **TestQualityGuard**: 自动审查测试代码质量

#### ⚡ 3. 性能与可靠性
- **LLMCache**: 缓存相似查询（降低 60-80% 成本）
- **LLMRetry**: 自动重试 + 熔断机制
- **FeedbackControlLoop**: 自动迭代直到质量达标
- **ExecutionGuard**: 超时/异常自动中止

#### 📊 4. 可观测性与治理
- **PerformanceMonitor**: P95/P99 延迟追踪
- **UsageTracker**: Token 用量统计
- **AuditLogger** (预览): SHA256 完整性操作日志
- **RBAC Engine** (预览): 15+ 权限点，5 种角色

#### 🔌 5. 集成与扩展
- **CLI**: 命令行工具（日常使用）
- **REST API**: FastAPI（系统集成）
- **Dashboard**: Streamlit Web UI（可视化）
- **MCP Protocol**: 接入 TRAE/Claude Code（AI Agent 生态）

---

## 📦 企业版特性（V3.6.6）

<details>
<summary>🏢 点击展开企业级功能</summary>

### 安全与合规
- ✅ **RBAC Engine** (Preview): 15+ 细粒度权限，5 种角色（SUPER_ADMIN/ADMIN/OPERATOR/ANALYST/VIEWER）
- ✅ **Audit Logger** (Preview): SHA256 完整性链，支持 CSV/JSON 导出
- ✅ **Multi-Tenancy** (Preview): 3 种隔离级别（Shared DB / Schema / DB per Tenant）
- ✅ **Sensitive Data Masker** (Preview): PII 数据自动脱敏

### 性能优化
- ✅ **AsyncIO Transformation**: 异步 LLM 调用，吞吐量提升 2x
- ✅ **Redis Cache Integration**: 三级缓存（L1 内存 → L2 Redis → L3 LLM），命中率 95%+
- ✅ **Prometheus Monitoring**: 12 个核心指标，`/metrics` 端点

### 质量保障
- ✅ **E2E Test Suite**: 16 个用户旅程测试用例，100% 通过率
- ✅ **2115+ Tests Passing**: 覆盖所有核心模块
- ✅ **65% Maturity Score (honest assessment)**: 企业级成熟度评分

</details>

---

## 🔄 对比：什么时候用 DevSquad？

| 你的需求 | 推荐方案 |
|---------|---------|
| 简单问答（"Python 怎么写 for 循环？"） | 直接用 ChatGPT/Claude ✅ |
| 代码片段审查 | DevSquad 单角色模式 ✅ |
| 复杂系统设计（需要多视角） | **DevSquad 多角色协作** 🎯 |
| 生产环境自动化流程 | **DevSquad + REST API + Dashboard** 🎯 |
| 团队协作标准流程 | **DevSquad + RBAC + Audit Log** 🎯 |

---

## 📖 想深入了解？

| 文档 | 适用人群 | 内容深度 |
|------|---------|---------|
| [README.md](README.md) | 所有用户 | 完整功能介绍 + 架构详解 |
| [SKILL.md](SKILL.md) | TRAE 用户 | 技能使用手册 + 70+ 模块参考 |
| [docs/i18n/SKILL_CN.md](docs/i18n/SKILL_CN.md) | 中文用户 | 中文版技能手册 |
| [docs/PRD.md](docs/PRD.md) | 产品经理 | 产品需求文档 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构师 | 技术架构文档 |
| [examples/](examples/) | 开发者 | 示例代码和最佳实践 |

---

## 🤝 支持与反馈

- 📕 **GitHub Issues**: [提交问题或建议](https://github.com/lulin70/DevSquad/issues)
- 💬 **Discussions**: [参与社区讨论](https://github.com/lulin70/DevSquad/discussions)
- 📧 **Email**: dev@lulin70.com

---

<p align="center">
  <strong>⭐ 如果 DevSquad 对你有帮助，请给个 Star！⭐</strong>
  <br>
  <em>让更多开发者享受到「AI 团队协作」的力量</em>
</p>

---

*最后更新: 2026-06-15 | 版本: V3.7.2*
