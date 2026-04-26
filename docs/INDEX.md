# DevSquad 文档索引

**最后更新**: 2026-04-26  
**版本**: v3.3.0

---

## 🚀 新用户必读

如果你是第一次使用 DevSquad，请按以下顺序阅读：

1. **[README.md](../README.md)** - 项目概述和快速开始
   - 什么是 DevSquad？
   - 5 分钟快速上手
   - 核心特性

2. **[INSTALL.md](../INSTALL.md)** - 安装和配置指南
   - 环境要求
   - 安装步骤
   - 配置 LLM Backend

3. **[EXAMPLES.md](../EXAMPLES.md)** - 真实使用示例
   - 架构设计场景
   - 多角色协作场景
   - 安全审计场景

**预计阅读时间**: 15-20 分钟

---

## 👨‍💻 开发者文档

如果你想贡献代码或深入了解 DevSquad：

### 核心文档

1. **[CONTRIBUTING.md](../CONTRIBUTING.md)** - 贡献指南
   - 如何提交 PR
   - 代码规范
   - 测试要求

2. **[architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md)** - 架构设计
   - Coordinator/Worker/Scratchpad 模式
   - LLM Backend 抽象层
   - 组件交互图

3. **[SKILL.md](../SKILL.md)** - Skill 集成说明
   - 如何在 Trae/Cline 中使用
   - Skill 配置
   - MCP 集成

### 角色系统

4. **[roles/](roles/)** - 角色定义和能力
   - 7 个核心角色
   - 角色别名映射
   - 角色能力矩阵

### 技术规范

5. **[spec/](spec/)** - 技术规范文档
   - API 规范
   - 数据模型
   - 协议定义

---

## 📊 项目管理

如果你想了解项目状态和规划：

### 当前状态

1. **[PROJECT_REVIEW_2026-04-26.md](PROJECT_REVIEW_2026-04-26.md)** - 最新项目评估
   - 项目健康度: 9.0/10
   - 核心功能状态
   - 优化建议

2. **[TEAM_CONSENSUS_OPTIMIZATION.md](TEAM_CONSENSUS_OPTIMIZATION.md)** - 团队优化共识
   - 优先级调整
   - 执行计划
   - 资源分配

### 发展路线

3. **[CHANGELOG.md](../CHANGELOG.md)** - 版本变更记录
   - v3.3.0 新特性
   - 历史版本
   - 破坏性变更

4. **[OPTIMIZATION_PLAN_KARPATHY.md](OPTIMIZATION_PLAN_KARPATHY.md)** - 优化方案
   - 基于 Karpathy 四大原则
   - 3 阶段优化计划
   - 预期成果

### 设计理念

5. **[KARPATHY_PRINCIPLES_INSIGHTS.md](KARPATHY_PRINCIPLES_INSIGHTS.md)** - 设计哲学
   - Think Before Coding
   - Simplicity First
   - Surgical Changes
   - Goal-Driven Execution

---

## 📚 参考资料

### 指南文档

- **[guide/](guide/)** - 使用指南和最佳实践
  - 如何设计好的任务描述
  - 如何选择合适的角色
  - 如何解读输出结果

### 归档文档

- **[archive/](archive/)** - 历史文档归档
  - 旧版本文档
  - 已废弃的设计
  - 历史决策记录

---

## 🔍 快速查找

### 按主题查找

| 主题 | 文档 | 说明 |
|------|------|------|
| **快速开始** | [README.md](../README.md) | 5 分钟上手 |
| **安装配置** | [INSTALL.md](../INSTALL.md) | 环境配置 |
| **使用示例** | [EXAMPLES.md](../EXAMPLES.md) | 真实场景 |
| **架构设计** | [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md) | 系统架构 |
| **贡献代码** | [CONTRIBUTING.md](../CONTRIBUTING.md) | 开发指南 |
| **角色系统** | [roles/](roles/) | 角色定义 |
| **Skill 集成** | [SKILL.md](../SKILL.md) | Trae/Cline 集成 |
| **项目状态** | [PROJECT_REVIEW_2026-04-26.md](PROJECT_REVIEW_2026-04-26.md) | 最新评估 |
| **优化计划** | [TEAM_CONSENSUS_OPTIMIZATION.md](TEAM_CONSENSUS_OPTIMIZATION.md) | 执行计划 |
| **版本历史** | [CHANGELOG.md](../CHANGELOG.md) | 变更记录 |

### 按角色查找

| 角色 | 推荐文档 |
|------|---------|
| **新用户** | README → INSTALL → EXAMPLES |
| **开发者** | CONTRIBUTING → ARCHITECTURE → SKILL |
| **产品经理** | PROJECT_REVIEW → TEAM_CS |
| **架构师** | ARCHITECTURE → OPTIMIZATION_PLAN → KARPATHY_PRINCIPLES |
| **测试工程师** | CONTRIBUTING → spec/ |

---

## 📝 文档维护

### 文档状态

| 文档 | 状态 | 最后更新 | 维护者 |
|------|------|---------|--------|
| README.md | ✅ 最新 | 2026-04-24 | PM |
| INSTALL.md | ✅ 最新 | 2026-04-24 | Arch |
| EXAMPLES.md | ✅ 最新 | 2026-04-24 | PM |
| ARCHITECTURE.md | ✅ 最新 | 2026-04-24 | Arch |
| PROJECT_REVIEW | ✅ 最新 | 2026-04-26 | All |
| TEAM_CONSENSUS | ✅ 最新 | 2026-04-26 | All |

### 文档更新规则

1. **核心文档**（README, INSTALL, EXAMPLES）: 每次发布前必须更新
2. **技术文档**（ARCHITECTURE, SKILL）: 架构变更时更新
3. **项目管理文档**（PROJECT_REVIEW, TEAM_CONSENSUS）: 每月更新
4. **归档文档**: 6 个月未更新的文档移到 archive/

---

## 🆘 获取帮助

### 常见问题

1. **找不到需要的文档？**
   - 使用本页面的"快速查找"表格
   - 搜索 docs/ 目录
   - 查看 archive/ 中的历史文档

2. **文档过时了？**
   - 提交 Issue 或 PR
   - 联系文档维护者
   - 查看 CHANGELOG 了解最新变更

3. **想贡献文档？**
   - 阅读 [CONTRIBUTING.md](../CONTRIBUTING.md)
   - 遵循文档规范
   - 提交 PR

### 联系方式

- **GitHub Issues**: https://github.com/your-org/DevSquad/issues
- **讨论区**: https://github.com/your-org/DevSquad/discussions
- **邮件**: devsquad@example.com

---

**提示**: 如果你是第一次使用 DevSquad，建议从"新用户必读"部分开始，按顺序阅读 3 个核心文档，大约需要 15-20 分钟。

**最后更新**: 2026-04-26 by 优化团队  
**下次审视**: 2026-05-26
