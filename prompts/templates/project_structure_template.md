# 项目目录结构规范模板 (Project Directory Structure Template)

## 概述

本模板定义了项目目录结构的标准规范。架构师在阶段2（架构设计）中必须根据项目类型选择对应的基础结构，并根据项目特点定制。独立开发者在阶段6（开发实现）中必须严格遵循此结构。

## 设计原则

1. **关注点分离**：不同类型的文件放在不同目录，职责清晰
2. **约定优于配置**：遵循行业惯例，减少认知负担
3. **可扩展性**：结构支持项目增长，不需要频繁重组
4. **可发现性**：新成员能快速找到需要的文件
5. **工具友好**：兼容主流构建工具、IDE、CI/CD

---

## 结构类型 A：Web 前端项目

```
{project-name}/
├── public/                         # 静态资源（不经过构建）
│   ├── favicon.ico
│   └── index.html
├── src/                            # 源代码
│   ├── assets/                     # 静态资源（经过构建）
│   │   ├── images/
│   │   ├── fonts/
│   │   └── styles/
│   │       ├── variables.css       # 设计令牌
│   │       ├── global.css          # 全局样式
│   │       └── animations.css      # 动画
│   ├── components/                 # 可复用组件
│   │   ├── ui/                     # 基础 UI 组件
│   │   │   ├── Button/
│   │   │   │   ├── Button.tsx
│   │   │   │   ├── Button.test.tsx
│   │   │   │   ├── Button.stories.tsx
│   │   │   │   └── index.ts
│   │   │   └── ...
│   │   ├── layout/                 # 布局组件
│   │   └── business/               # 业务组件
│   ├── features/                   # 功能模块（按业务域组织）
│   │   ├── auth/                   # 认证模块
│   │   │   ├── components/
│   │   │   ├── hooks/
│   │   │   ├── services/
│   │   │   ├── types.ts
│   │   │   └── index.ts
│   │   └── ...
│   ├── hooks/                      # 通用自定义 Hooks
│   ├── services/                   # API 服务层
│   │   ├── api.ts                  # API 客户端配置
│   │   └── {domain}.ts            # 按领域分文件
│   ├── stores/                     # 状态管理
│   ├── utils/                      # 工具函数
│   ├── types/                      # TypeScript 类型定义
│   │   ├── api.d.ts
│   │   └── global.d.ts
│   ├── App.tsx                     # 应用入口
│   └── main.tsx                    # 渲染入口
├── tests/                          # 测试
│   ├── e2e/                        # 端到端测试
│   ├── integration/                # 集成测试
│   └── fixtures/                   # 测试数据
├── docs/                           # 项目文档
│   ├── architecture/               # 架构文档
│   ├── api/                        # API 文档
│   └── guides/                     # 使用指南
├── config/                         # 配置文件
│   ├── dev.ts
│   ├── staging.ts
│   └── production.ts
├── .env.example                    # 环境变量模板
├── .gitignore
├── package.json
├── tsconfig.json
├── vite.config.ts                  # 或 webpack.config.js
└── README.md
```

---

## 结构类型 B：后端服务项目

```
{project-name}/
├── src/                            # 源代码
│   ├── main/                       # 主代码
│   │   ├── controllers/            # 控制器（HTTP 入口）
│   │   ├── services/               # 业务逻辑
│   │   ├── repositories/           # 数据访问
│   │   ├── models/                 # 数据模型
│   │   ├── dto/                    # 数据传输对象
│   │   ├── config/                 # 配置
│   │   ├── middleware/             # 中间件
│   │   ├── utils/                  # 工具函数
│   │   └── app.ts                  # 应用入口
│   └── test/                       # 测试代码
│       ├── unit/                   # 单元测试
│       ├── integration/            # 集成测试
│       └── fixtures/               # 测试数据
├── migrations/                     # 数据库迁移
├── scripts/                        # 运维脚本
│   ├── seed.ts                     # 数据填充
│   └── deploy.sh                   # 部署脚本
├── docs/                           # 项目文档
│   ├── api/                        # API 文档
│   ├── architecture/               # 架构文档
│   └── runbook/                    # 运维手册
├── config/                         # 配置文件
│   ├── default.yaml
│   ├── development.yaml
│   ├── staging.yaml
│   └── production.yaml
├── deploy/                         # 部署配置
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── k8s/                        # Kubernetes 配置
├── .env.example
├── .gitignore
├── package.json                    # 或 pom.xml / requirements.txt / Cargo.toml
└── README.md
```

---

## 结构类型 C：全栈项目

```
{project-name}/
├── packages/                       # Monorepo 包管理
│   ├── web/                        # 前端（结构同类型 A）
│   ├── server/                     # 后端（结构同类型 B）
│   ├── shared/                     # 共享代码
│   │   ├── types/                  # 共享类型
│   │   ├── utils/                  # 共享工具
│   │   └── constants/              # 共享常量
│   └── cli/                        # CLI 工具（如有）
├── docs/                           # 项目文档
│   ├── architecture/
│   ├── api/
│   └── guides/
├── scripts/                        # 脚本
├── deploy/                         # 部署配置
├── .github/                        # GitHub 配置
│   └── workflows/                  # CI/CD
├── .env.example
├── .gitignore
├── package.json                    # 根 package.json（workspace）
├── turbo.json                      # 或 lerna.json / nx.json
└── README.md
```

---

## 结构类型 D：Python 项目

```
{project-name}/
├── src/                            # 源代码
│   └── {package_name}/            # Python 包
│       ├── __init__.py
│       ├── core/                   # 核心逻辑
│       ├── api/                    # API 层
│       ├── models/                 # 数据模型
│       ├── services/               # 业务逻辑
│       ├── repositories/           # 数据访问
│       ├── utils/                  # 工具函数
│       └── config/                 # 配置
├── tests/                          # 测试
│   ├── unit/
│   ├── integration/
│   ├── conftest.py                 # pytest 配置
│   └── fixtures/
├── scripts/                        # 脚本
├── docs/                           # 文档
├── migrations/                     # 数据库迁移（如有）
├── pyproject.toml                  # 项目配置
├── requirements.txt                # 依赖
├── setup.py                        # 或 setup.cfg
├── .env.example
├── .gitignore
└── README.md
```

---

## 结构类型 E：AI/ML 项目

```
{project-name}/
├── src/                            # 源代码
│   ├── data/                       # 数据处理
│   │   ├── ingestion.py
│   │   ├── preprocessing.py
│   │   └── validation.py
│   ├── features/                   # 特征工程
│   ├── models/                     # 模型定义
│   │   ├── train.py
│   │   ├── evaluate.py
│   │   └── predict.py
│   ├── pipelines/                  # ML 管道
│   ├── serving/                    # 模型服务
│   └── utils/
├── notebooks/                      # Jupyter 笔记本
│   ├── exploration/
│   └── experiments/
├── experiments/                    # 实验记录
├── configs/                        # 训练配置
│   ├── model_config.yaml
│   ├── train_config.yaml
│   └── serving_config.yaml
├── artifacts/                      # 模型产物（.gitignore）
│   ├── models/
│   └── checkpoints/
├── data/                           # 数据目录（.gitignore）
│   ├── raw/
│   ├── processed/
│   └── external/
├── tests/
├── docs/
├── .env.example
├── .gitignore
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## 通用规范

### 必须存在的目录和文件

| 目录/文件 | 说明 | 必须性 |
|-----------|------|--------|
| `src/` | 源代码 | ✅ 必须 |
| `tests/` | 测试代码 | ✅ 必须 |
| `docs/` | 项目文档 | ✅ 必须 |
| `.gitignore` | Git 忽略规则 | ✅ 必须 |
| `README.md` | 项目说明 | ✅ 必须 |
| `.env.example` | 环境变量模板 | ✅ 必须 |
| `config/` | 配置文件 | ✅ 推荐 |
| `scripts/` | 脚本 | 🟡 推荐 |

### 必须不存在的目录和文件

| 目录/文件 | 说明 | 原因 |
|-----------|------|------|
| `__pycache__/` | Python 缓存 | 应在 .gitignore |
| `.cache/` | 通用缓存 | 应在 .gitignore |
| `node_modules/` | Node 依赖 | 应在 .gitignore |
| `dist/` / `build/` | 构建产物 | 应在 .gitignore |
| `.env` | 环境变量 | 包含敏感信息，.gitignore |
| 临时文件 | `*.tmp`, `*.log` | 应在 .gitignore |

### .gitignore 必须包含

```gitignore
# 依赖
node_modules/
.venv/
venv/
__pycache__/

# 构建产物
dist/
build/
*.pyc
*.pyo

# 环境变量
.env
.env.local
.env.*.local

# IDE
.idea/
.vscode/
*.swp

# 系统文件
.DS_Store
Thumbs.db

# 日志
*.log
logs/

# 测试覆盖率
coverage/
htmlcov/
.coverage

# 运行时数据
data/
*.db
*.sqlite
```

---

## 架构师使用指南

在阶段2（架构设计）中，架构师必须：

1. **选择基础结构类型**：根据项目类型选择 A/B/C/D/E
2. **定制目录结构**：根据项目特点调整目录
3. **输出项目目录结构文档**：作为架构设计文档的一部分
4. **定义命名规范**：文件命名、目录命名规则
5. **定义模块边界**：每个目录的职责和边界

### 输出格式

```markdown
# 项目目录结构

## 基础类型
{选择的结构类型}

## 定制结构
{基于基础类型定制的目录树}

## 命名规范
- 文件命名：{规则}
- 目录命名：{规则}
- 组件命名：{规则}

## 模块边界
| 目录 | 职责 | 依赖方向 | 禁止依赖 |
|------|------|---------|---------|
| src/components | UI 组件 | → hooks, utils | ← features, services |
| src/features | 业务功能 | → components, services | ← 其他 features |
| src/services | API 服务 | → types, config | ← components, features |

## 约束
1. {约束1}
2. {约束2}
```

## 独立开发者使用指南

在阶段6（开发实现）中，独立开发者必须：

1. **严格遵循目录结构**：不创建结构外的文件
2. **遵循命名规范**：文件和目录命名符合规范
3. **遵守模块边界**：不违反依赖方向约束
4. **新文件放对位置**：每个新文件都在正确的目录中
