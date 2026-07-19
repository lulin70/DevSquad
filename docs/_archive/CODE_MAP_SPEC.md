# ARCHIVED TEMPLATE — Code Map Generator 规范

> **归档时间**: 2026-07-19 (V4.1.1 WorkBuddy Review Action Plan P1-8)
> **归档原因**: 此文档为通用代码地图生成器模板（Java/Spring 示例），未填充 DevSquad 实际结构。
> **替代文档**: [docs/spec/PROJECT_STRUCTURE.md](../spec/PROJECT_STRUCTURE.md) — 已填充 DevSquad 实际项目结构
> **状态**: ARCHIVED — 不再维护，仅作历史参考保留

---

# 代码地图生成器 (Code Map Generator) — 原始模板内容

> ⚠️ 以下内容为通用模板示例，与 DevSquad 实际结构无关。请参考 [PROJECT_STRUCTURE.md](../spec/PROJECT_STRUCTURE.md) 获取 DevSquad 真实结构。

## 功能概述

代码地图生成器是一个用于快速理解超大型系统代码结构的工具。它能够：

1. **扫描项目结构**: 自动发现所有源代码文件、配置文件
2. **分析代码元素**: 提取类、函数、接口、模块等信息
3. **生成调用关系**: 追踪代码间的调用依赖关系
4. **构建架构视图**: 按照分层架构组织代码
5. **输出 md 格式**: 生成人类和 AI 均可阅读的代码地图文档

## 核心概念

### 节点类型 (Node Types)

| 类型 | 说明 | ID 格式 |
|------|------|---------|
| `file` | 源代码文件 | `file:<相对路径>` |
| `function` | 函数或方法 | `function:<相对路径>:<函数名>` |
| `class` | 类、接口、类型 | `class:<相对路径>:<类名>` |
| `module` | 逻辑模块或包 | `module:<模块名>` |
| `config` | 配置文件 | `config:<相对路径>` |

### 边类型 (Edge Types)

| 类别 | 类型 | 说明 |
|------|------|------|
| Structural | `imports` | 模块导入关系 |
| Structural | `exports` | 模块导出关系 |
| Structural | `contains` | 包含关系（文件包含函数/类） |
| Behavioral | `calls` | 函数调用关系 |
| Behavioral | `creates` | 对象创建关系 |
| Data Flow | `reads_from` | 读取数据源 |
| Data Flow | `writes_to` | 写入数据目标 |
| Dependencies | `depends_on` | 依赖关系 |
| Dependencies | `configures` | 配置关系 |

### 架构层级 (Architecture Layers)

| 层级 | 说明 | 目录模式 |
|------|------|----------|
| API Layer | HTTP 端点、路由处理、控制器 | routes, controller, handler, endpoint, api |
| Service Layer | 业务逻辑、应用服务 | service, usecase, business |
| Data Layer | 数据模型、数据库访问、持久化 | model, entity, schema, database, db, repository, repo |
| UI Layer | 用户界面组件和视图 | component, view, page, screen, layout, widget, ui |
| Middleware Layer | 请求/响应中间件和拦截器 | middleware, interceptor, guard, filter, pipe |
| Utility Layer | 共享工具、帮助库 | util, helper, lib, common, shared |
| Config Layer | 应用配置和环境设置 | config, setting, env |
| Test Layer | 测试文件和测试工具 | test, spec |

## 使用方法

### 基本用法

```bash
# 分析当前项目
python -m code_map_generator .

# 分析指定项目
python -m code_map_generator /path/to/project

# 指定输出文件
python -m code_map_generator /path/to/project --output code-map.md

# 仅分析特定目录
python -m code_map_generator /path/to/project --scope src/api
```

### 作为 Agent 记忆使用

将生成的 `code-map.md` 文件路径添加到 agent 的上下文中，agent 就能快速理解项目结构。

### 作为项目规则使用

将 `code-map.md` 放到项目根目录或 `.trae/rules/` 目录中，作为项目知识的一部分。

---

> **归档说明结束**: 此文档保留作历史参考。DevSquad 实际项目结构请查阅 [PROJECT_STRUCTURE.md](../spec/PROJECT_STRUCTURE.md)。
