# DevSquad — 多角色 AI 任务编排器

<p align="center">
  <strong>一个任务 → 多角色AI协作 → 一个结论</strong>
  <br>
  <em>生产就绪 | V3.4.0</em>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Tests" src="https://img.shields.io/badge/Tests-1478%20passing%20(98.4%25)-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V3.4.0--Prod-success" />
  <img alt="CI" src="https://img.shields.io/badge/CI-GitHub_Actions-blue?logo=githubactions" />
  <img alt="Quality" src="https://img.shields.io/badge/Code%20Quality-4.3%2F5%20%E2%98%85%E2%98%85%E2%98%85%E2%98%85%E2%98%86-blue" />
  <img alt="Security" src="https://img.shields.io/badge/Security-5%2F5%20%E2%98%85%E2%98%85%E2%98%85%E2%98%85%E2%98%85-success" />
</p>

---

## 🚀 V3.4.0-Prod: 生产就绪版本

**DevSquad 现已达到生产就绪状态！** 完整支持认证、REST API、告警和历史数据存储。

### 🎯 快速开始（3种使用方式）

#### 1️⃣ 交互式 Web 仪表板（推荐）
```bash
# 启动带认证的 Streamlit 仪表板
streamlit run scripts/dashboard.py

# 打开 http://localhost:8501
# 使用 admin / admin123 登录
```

#### 2️⃣ REST API 服务器
```bash
# 安装依赖
pip install fastapi uvicorn

# 启动 API 服务器
uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000 --reload

# 访问 Swagger UI: http://localhost:8000/docs
# 访问 ReDoc:      http://localhost:8000/redoc
```

#### 3️⃣ 命令行界面
```bash
# 标准 CLI 用法
python scripts/cli.py lifecycle build

# 增强的可视化输出
python scripts/cli.py lifecycle build --visual --verbose
```

---

## 🏗️ 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    用户访问层                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ Streamlit    │ │ FastAPI REST │ │ CLI/Notebook │        │
│  │ 仪表板       │ │ API 服务器   │ │ (现有)       │        │
│  │ (Auth+HTTPS) │ │ (Swagger)    │ │              │        │
│  └──────┬───────┘ └──────┬───────┘ └──────────────┘        │
└─────────┼───────────────┼───────────────────────────────────┘
          │               │
          ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│                   业务逻辑层                                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │AuthManager  │ │AlertManager │ │HistoryMgr   │           │
│  │(RBAC 认证)  │ │(多通道)     │ │(SQLite TSDB)│           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│  ┌─────────────────────────────────────────────┐            │
│  │     LifecycleProtocol (11阶段引擎)           │            │
│  │     UnifiedGateEngine + CheckpointManager     │            │
│  └─────────────────────────────────────────────┘            │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    数据持久层                               │
│  ┌────────────┐ ┌────────────┐ ┌────────────────────────┐  │
│  │ SQLite DB  │ │ YAML 配置  │ │ 检查点文件             │  │
│  │ (历史)     │ │ (部署)      │ │ (生命周期状态)         │  │
│  └────────────┘ └────────────┘ └────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## ✨ 核心特性 (V3.4.0)

### 🧩 关注点增强包 (NEW)
领域专属知识包，根据任务内容自动增强AI角色提示词：
- **权限设计增强包** — RBAC/ABAC/ReBAC/ACL决策框架，行级/列级权限模式，7个常见陷阱（IDOR、权限提升、缓存残留...）
- **Web API设计增强包** — REST/GraphQL/gRPC风格选择，JWT/OAuth2/API Key认证，版本管理策略，限流，RFC 7807错误处理
- **数据管道增强包** — 批处理/流处理/CDC管道模式，幂等性保证，数据质量框架，Schema演化，增量同步策略

增强包通过关键词**自动匹配**且**可组合** — "多租户API权限"任务会同时激活权限+Web API两个增强包。

### 🎯 交互式设置向导 (NEW)
```bash
devsquad init    # 5步引导设置（1-2分钟）
# Step 1: 项目类型（Web API / 全栈 / CLI / ML / 库 / 通用）
# Step 2: AI后端（Mock / OpenAI / Anthropic）
# Step 3: 默认角色（根据项目类型自动推荐）
# Step 4: 语言和功能
# Step 5: 保存到 ~/.devsquad.yaml
```

### 💬 用户友好的错误提示 (NEW)
技术错误现在翻译为人类可读的提示，附带修复建议和使用示例：
```
❌ 之前: "Input validation failed: Task too short (min 5 chars, got 2)"
✅ 现在: "任务描述太短了，请详细说明你想做什么"
         "💡 好的任务描述应该包含：做什么 + 为什么 + 有什么特殊要求"
         "📝 示例: devsquad dispatch -t '设计一个支持手机号和邮箱登录的用户认证系统'"
```

### 📊 性能监控 (NEW)
内置性能监控，包含滑动窗口统计、阈值告警和回归检测：
- 每次调度自动收集指标（11步骤计时明细）
- P50/P95/P99延迟分析
- 性能回归检测（>20%恶化触发告警）
- 导出指标到JSON供外部仪表盘使用

### 🤖 多角色协作系统

| 角色 | 职责 | 触发关键词 |
|------|------|------------|
| **架构师** | 架构设计、技术选型 | architecture, design, performance |
| **产品经理** | 需求分析、PRD撰写 | requirements, PRD, user story |
| **安全专家** | 威胁建模、安全审计 | security, vulnerability, audit |
| **测试专家** | 测试策略、质量保证 | test, quality, automation |
| **开发** | 功能实现、代码审查 | implementation, code, fix |
| **运维工程师** | CI/CD、部署、监控 | CI/CD, deploy, Docker, monitoring |
| **UI设计师** | UI设计、交互原型 | UI, interface, prototype |

### 🔒 安全特性

- ✅ **RBAC 认证系统**: Admin / Operator / Viewer 三级角色
- ✅ **输入验证**: 16种攻击模式检测（XSS/SQL注入/提示词注入）
- ✅ **权限控制**: 4级权限（PLAN/DEFAULT/AUTO/BYPASS）
- ✅ **HTTPS 支持**: TLS 1.2+ 加密传输
- ✅ **审计日志**: 完整的操作追踪记录

### ⚡ 性能优化

- ✅ **LLM 缓存**: 内存+磁盘双层缓存，减少API调用60-80%
- ✅ **上下文压缩**: 4级压缩策略防止溢出
- ✅ **并行执行**: ThreadPoolExecutor 多Worker并发
- ✅ **启动预热**: 3层预加载机制减少冷启动延迟

---

## 📦 安装与配置

### 前置条件

- Python 3.9+
- pip 或 pipenv

### 安装步骤

```bash
# 克隆仓库
git clone https://github.com/your-org/devsquad.git
cd devsquad

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 运行测试
pytest tests/ -v

# 启动应用
python scripts/cli.py dispatch -t "测试任务"
```

---

## 🧪 测试覆盖

| 类别 | 测试数 | 通过率 |
|------|--------|--------|
| 核心模块 (Dispatcher/Coordinator/Worker) | 39 | 100% |
| 角色匹配 (RoleMatcher/Semantic) | 25 | 100% |
| 上游模块 (Checkpoint/Workflow) | 35 | 100% |
| MCEAdapter (CarryMem集成) | 30 | 100% |
| CLI 生命周期 | 28 | 100% |
| UX 报告格式 | 24 | 100% |
| **总计** | **1478** | **98.4%** |

---

## 📚 文档资源

| 文档 | 语言 | 描述 |
|------|------|------|
| [README.md](./README.md) | English | 主文档（本文件） |
| [README-CN.md](./README-CN.md) | 中文 | 本文档 |
| [README-JP.md](./README-JP.md) | 日本語 | 日语版文档 |
| [SKILL.md](./SKILL.md) | English | Skill 使用指南 |
| [CHANGELOG.md](./CHANGELOG.md) | English | 版本变更日志 |
| [docs/](./docs/) | English | 详细技术文档 |

---

## 🎮 使用示例

### 示例1: 快速协作（Mock模式）

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch("设计用户认证系统")
print(result.to_markdown())
disp.shutdown()
```

### 示例2: 使用真实 LLM 后端

```python
import os
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.llm_backend import create_backend

backend = create_backend(
    "openai",
    api_key=os.environ["OPENAI_API_KEY"],
    model="gpt-4",
)

disp = MultiAgentDispatcher(llm_backend=backend)
result = disp.dispatch("实现微服务架构", roles=["architect", "security"])
print(result.to_markdown())
disp.shutdown()
```

### 示例3: CLI 生命周期命令

```bash
# 规格阶段
python scripts/cli.py lifecycle spec -t "电商系统需求"

# 规划阶段
python scripts/cli.py lifecycle plan -t "数据库设计方案"

# 构建阶段
python scripts/cli.py lifecycle build -t "实现支付接口"

# 测试阶段
python scripts/cli.py lifecycle test -t "单元测试套件"

# 审查阶段
python scripts/cli.py lifecycle review -t "代码审查"

# 发布阶段
python scripts/cli.py lifecycle ship -t "v2.0发布"
```

---

## 🛠️ 开发指南

### 项目结构

```
DevSquad/
├── scripts/
│   ├── collaboration/          # 核心协作模块 (27个)
│   │   ├── dispatcher.py       # 统一调度入口
│   │   ├── coordinator.py      # 全局编排器
│   │   ├── worker.py           # Worker执行者
│   │   ├── scratchpad.py       # 共享黑板
│   │   ├── consensus.py        # 共识引擎
│   │   ├── permission_guard.py # 权限控制
│   │   ├── llm_cache.py        # 缓存系统
│   │   ├── input_validator.py  # 输入验证
│   │   └── ...
│   ├── cli.py                 # 命令行界面
│   ├── dashboard.py           # Streamlit仪表板
│   └── api_server.py          # FastAPI服务器
├── tests/                     # 测试套件 (1478个)
├── docs/                      # 文档
├── SKILL.md                   # Skill定义
├── CHANGELOG.md              # 变更日志
└── README.md                 # 英文主文档
```

### 代码规范

- **类型注解**: Python 3.8+ 类型提示
- **文档字符串**: Google风格 docstring
- **异常处理**: 具体异常类型 + 异常链保留
- **日志级别**: DEBUG/INFO/WARNING/ERROR/CRITICAL

---

## 📈 性能基准

| 操作 | 平均耗时 | P99 | 目标 |
|------|----------|-----|------|
| Dispatcher 初始化 | ~1.3s | 2.5s | <2s |
| 单次 Dispatch (Mock) | ~120ms | 250ms | <500ms |
| Worker 执行 | ~80ms | 150ms | <200ms |
| 共识决策 | ~45ms | 90ms | <100ms |
| 内存占用 | ~85MB | 150MB | <200MB |

---

## 🤝 贡献指南

我们欢迎社区贡献！请遵循以下步骤：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### 开发流程

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行代码检查
flake8 scripts/
mypy scripts/

# 运行完整测试
pytest tests/ -v --cov=scripts/collaboration

# 运行性能基准
pytest tests/test_performance_benchmarks.py --benchmark-only
```

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

---

## 🙏 致谢

感谢以下开源项目：
- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Web API 框架
- [Streamlit](https://streamlit.io/) - 数据科学 Web 应用框架
- [Pydantic](https://pydantic-docs.helpmanual.io/) - 数据验证库
- [Click](https://click.palletsprojects.com/) - 命令行工具库

---

<p align="center">
  <strong>Made with ❤️ by DevSquad Team</strong>
  <br>
  <em>多角色AI协作，让每个任务都得到专业处理</em>
</p>

<p align="center">
  <a href="#top">回到顶部 ↑</a>
</p>
