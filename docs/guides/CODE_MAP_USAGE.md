# 代码地图生成器使用指南

## 概述

代码地图生成器用于快速为 agent 生成项目代码结构文档，帮助 agent 快速理解项目架构、定位需要修复的代码文件。

## 使用场景

1. **新项目接手**: 当 agent 需要理解一个陌生的超大型项目时
2. **代码修复**: 当 agent 需要快速定位 bug 所在文件时
3. **架构理解**: 当 agent 需要理解系统的分层架构时
4. **依赖追踪**: 当 agent 需要理解模块间的调用关系时

## 使用方法

### 方式一：命令行直接调用

```bash
# 基本用法
python /Users/wangwei/claw/.trae/skills/trae-multi-agent/scripts/code_map_generator_v2.py <项目路径>

# 指定工作空间 (用于多项目 workspace)
python /Users/wangwei/claw/.trae/skills/trae-multi-agent/scripts/code_map_generator_v2.py <项目路径> --workspace <工作空间路径>

# 指定输出文件
python /Users/wangwei/claw/.trae/skills/trae-multi-agent/scripts/code_map_generator_v2.py <项目路径> --output <输出路径>

# 仅分析特定目录
python /Users/wangwei/claw/.trae/skills/trae-multi-agent/scripts/code_map_generator_v2.py <项目路径> --scope src/api
```

### 多项目 Workspace 场景

当一个 workspace 包含多个项目时，使用 `--workspace` 参数可以明确项目所属的工作空间：

```bash
# workspace 结构:
# /workspace/
#   ├── project-a/  (项目 A)
#   └── project-b/  (项目 B)

# 生成项目 A 的代码地图 (自动检测 workspace 为父目录)
python code_map_generator_v2.py /workspace/project-a
# 输出: project-a-CODE_MAP.md
# workspace 字段显示: "workspace"

# 显式指定 workspace
python code_map_generator_v2.py /workspace/project-a --workspace /workspace
# workspace 字段显示: "workspace"
# relative_path 字段显示: "project-a"
```

### 方式二：在 Agent 流程中调用

在 agent 工作流中，可以使用以下 prompt 调用代码地图生成器：

```
请先生成项目代码地图，以便我更好地理解代码结构：
- 项目路径: <项目路径>
- 工作空间路径: <工作空间路径> (可选)
- 执行命令: python /Users/wangwei/claw/.trae/skills/trae-multi-agent/scripts/code_map_generator_v2.py <项目路径> --workspace <工作空间路径>
- 生成的代码地图将保存到项目根目录的 CODE_MAP.md 文件
```

### 方式三：作为技能调用

将以下内容添加到 skill 的执行流程中：

```yaml
- name: generate-code-map
  description: 生成项目代码地图
  script: |
    python /Users/wangwei/claw/.trae/skills/trae-multi-agent/scripts/code_map_generator_v2.py {{project_root}} --workspace {{workspace_root}} --output {{project_root}}/CODE_MAP.md
  output: CODE_MAP.md
```

## 代码地图内容

生成的代码地图包含以下内容：

1. **项目概览**: 项目名称、路径、技术栈、代码规模等基本信息
2. **架构分层**: 按分层架构组织的代码视图（API Layer, Service Layer, Data Layer 等）
3. **模块详情**: 按模块组织的代码文件列表
4. **文件详情**: 关键文件的详细分析，包括函数签名、调用关系等
5. **配置文件**: 项目的配置文件内容和说明
6. **调用流程图**: 典型的调用链和模块依赖关系
7. **快速修复指南**: 针对常见问题的排查路径

## 代码地图作为 Agent 记忆

生成代码地图后，可以将其作为 agent 的上下文记忆使用：

```markdown
在开始之前，请先阅读项目代码地图：
[读取 CODE_MAP.md 文件内容]

根据代码地图，我现在了解到：
1. 项目分为 X 个架构层
2. 核心模块位于 src/ 目录
3. API 路由位于 routes/ 目录
4. ...
```

## 最佳实践

1. **首次接触项目**: 先生成代码地图，快速了解项目结构
2. **定位 bug**: 利用代码地图中的"快速修复指南"快速定位问题
3. **理解调用链**: 使用"调用流程图"理解代码的执行路径
4. **代码修改**: 根据架构分层信息，确定修改的影响范围

## 输出示例

```
# myproject 代码地图

> 生成时间: 2026-03-28 10:30:00
> 代码版本: abc1234
> 分析文件数: 150

---

## 项目概览

- 项目名称: myproject
- 技术栈: python, javascript
- 框架: Django, React
- 代码规模: large

## 架构分层

| 架构层级 | 文件数 | 说明 |
|----------|--------|------|
| API Layer | 25 | HTTP 端点、路由处理 |
| Service Layer | 40 | 业务逻辑 |
| Data Layer | 30 | 数据持久化 |
| ...
```

## 注意事项

1. 代码地图生成可能需要一些时间，特别是对于大型项目
2. 生成的代码地图是基于静态分析的，可能不完全反映运行时行为
3. 建议在代码结构发生重大变化后重新生成代码地图
4. 代码地图可以直接作为 agent 记忆或项目规则使用