# DevSquad 使用示例

> **版本**: V4.4.1 | **最后验证**: 2026-07-30, DevSquad V4.4.1, backend=mock + openai(rsxermu666.cn)
>
> **Production Ready**: Authentication ✅ | REST API ✅ | Alert System ✅ | Historical Data ✅
>
> **V4.4.0 新增模块示例**: RiskRegister / ViewpointRegistry / ErrorBudgetTracker / GapAnalyzer / DoraMetricsCollector（见 [§V4.4.0 新模块示例](#v440-新模块示例)）

## 快速开始 (3种方式)

### 方式1: CLI命令行 (传统方式)

```bash
# Mock 模式（默认）— 无需 API Key
python3 scripts/cli.py dispatch -t "设计用户认证系统"

# 真实 AI 输出 — 先设置环境变量
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.moka-ai.com/v1"
export OPENAI_MODEL="gpt-4"
python3 scripts/cli.py dispatch -t "设计用户认证系统" --backend openai

# 指定角色（短 ID: arch/pm/test/coder/ui/infra/sec）
python3 scripts/cli.py dispatch -t "设计用户认证系统" -r arch pm test --backend openai

# 流式输出（实时查看 LLM 响应）
python3 scripts/cli.py dispatch -t "设计用户认证系统" -r arch --backend openai --stream

# Dry-run（模拟不执行）
python3 scripts/cli.py dispatch -t "设计用户认证系统" --dry-run
```

### 方式2: Web仪表板 (V3.6.0) 🎨

```bash
# 启动Streamlit Dashboard (带认证)
streamlit run scripts/dashboard.py

# 打开 http://localhost:8501
# 登录: 使用默认开发凭证（见 INSTALL.md "Default credentials" 章节）
# 生产环境必须修改所有默认密码
```

**Dashboard功能**:
- 📊 实时生命周期阶段监控
- 🔗 CLI命令到11阶段映射可视化
- 🚧 Gate状态追踪与显示
- 📈 性能指标展示（响应时间、成功率等）
- 👥 多用户登录与会话管理

### 方式3: REST API (V3.6.0) 🌐

```bash
# 安装API依赖
pip install -e ".[api]"

# 启动FastAPI服务器
uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000 --reload

# 访问Swagger文档: http://localhost:8000/docs
```

**API使用示例**:

```bash
# 获取所有生命周期阶段
curl http://localhost:8000/api/v1/lifecycle/phases | jq '.[] | {phase_id, name, status}'

# 获取当前状态
curl http://localhost:8000/api/v1/lifecycle/status | jq

# 执行阶段操作
curl -X POST http://localhost:8000/api/v1/lifecycle/actions \
  -H "Content-Type: application/json" \
  -d '{"phase_id": "P8", "action": "advance"}'

# 获取实时指标
curl http://localhost:8000/api/v1/metrics/current | jq

# 检查所有Gate状态
curl http://localhost:8000/api/v1/gates/status | jq '{total, passing, failing}'

# 健康检查
curl http://localhost:8000/api/v1/health | jq '{status, version, uptime_seconds}'
```

---

### 示例 1：架构设计（单角色）

```bash
python3 scripts/cli.py dispatch \
    -t "设计一个带 OAuth2 和 2FA 的用户认证系统" \
    -r arch --backend openai
```

**真实输出** (验证于 2026-04-24, 91s, architect 角色):

```
# OAuth2 + 2FA 用户认证系统架构设计

## 核心发现

1. **分层隔离是安全基础** - OAuth2 授权层与 2FA 验证层必须独立部署，
   避免单点攻击面，token 存储与验证逻辑物理隔离
2. **性能与安全的平衡点** - Redis 集群缓存 token（TTL 15min）+
   数据库持久化 refresh token（30天），配合 rate limiting 防暴力破解
```

### 示例 2：多角色协作

```bash
python3 scripts/cli.py dispatch \
    -t "为 SaaS 平台构建实时聊天功能" \
    -r arch pm test --backend openai
```

**真实输出** (验证于 2026-04-24, 144s, 3 个角色):

- **架构师**: WebSocket + Redis Pub/Sub 架构方案，支持百万级并发，
  延迟 <50ms，消息持久化与实时传输解耦
- **产品经理**: 实时聊天功能 PRD，核心业务价值（提升协作效率、增强平台粘性），
  目标用户（B端SaaS团队协作场景）
- **测试专家**: 测试方案，核心风险点（WebSocket 稳定性、消息延迟 <500ms、
  并发负载），数据一致性多层验证，安全合规早期介入

### 示例 3：安全审计

```bash
python3 scripts/cli.py dispatch \
    -t "对处理用户支付和个人数据的 REST API 进行安全审计" \
    -r sec --backend openai
```

**真实输出** (验证于 2026-04-24, 48s, security 角色):

```
I'll conduct a comprehensive security audit for your REST API handling
payments and personal data. Since I don't have access to your actual
codebase, I'll provide an executable audit framework with...
```

### 示例 4：流式输出（V3.6.0）

```bash
python3 scripts/cli.py dispatch \
    -t "设计微服务电商后端" \
    -r arch --backend openai --stream
```

流式模式下，LLM 响应会实时逐块输出到终端，无需等待完整响应。
适合长时间生成的内容，可以提前看到结果并随时中断。

### 示例 5：共识模式

```bash
python3 scripts/cli.py dispatch \
    -t "为分析平台选择数据库" \
    -r arch sec \
    --mode consensus
```

共识模式在角色意见不一致时强制投票。每个角色投加权票，否决权受尊重，
死锁时可升级人工裁决。

### 示例 6：JSON 输出（自动化集成）

```bash
python3 scripts/cli.py dispatch \
    -t "审查代码库性能问题" \
    -r arch coder \
    --format json
```

JSON 输出是机器可读格式，适合 CI/CD 流水线或后续处理。

## Docker 使用

```bash
# 构建镜像
docker build -t devsquad .

# Mock 模式运行
docker run devsquad dispatch -t "设计认证系统"

# 带 API Key 运行
docker run -e OPENAI_API_KEY="sk-..." devsquad dispatch -t "设计认证系统" --backend openai

# 交互式终端
docker run -it devsquad /bin/bash
```

## 配置文件使用

创建 `~/.devsquad.yaml`:

```yaml
devsquad:
  backend: openai
  base_url: https://api.openai.com/v1
  model: gpt-4
  timeout: 120
  output_format: structured
  strict_validation: false
  checkpoint_enabled: true
  cache_enabled: true
  log_level: WARNING
```

优先级: 环境变量 > 配置文件 > 默认值

```bash
# 配置文件设置后，无需每次指定 --backend
python3 scripts/cli.py dispatch -t "设计认证系统"
# 自动使用配置文件中的 openai 后端
```

## 系统命令

```bash
# 列出所有可用角色
python3 scripts/cli.py roles

# 显示系统状态
python3 scripts/cli.py status

# JSON 格式列出角色
python3 scripts/cli.py roles --format json

# 显示版本
python3 scripts/cli.py --version    # 3.6.0
```

## Python API 示例

### 基础调度（带真实 LLM 后端）

```python
import os
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.llm_backend import create_backend

backend = create_backend(
    "openai",
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ.get("OPENAI_BASE_URL"),
    model=os.environ.get("OPENAI_MODEL", "gpt-4"),
)

disp = MultiAgentDispatcher(llm_backend=backend)
result = disp.dispatch(
    "设计用户认证系统",
    roles=["architect", "pm", "tester"],
    mode="auto",
)

print(result.summary)
print(result.to_markdown())
disp.shutdown()
```

### Mock 模式（无需 API Key）

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch(
    "设计用户认证系统",
    roles=["architect", "pm", "tester"],
)

print(result.summary)
disp.shutdown()
```

### 流式输出（Python API）

```python
import os
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.llm_backend import create_backend

backend = create_backend("openai", api_key=os.environ["OPENAI_API_KEY"])
disp = MultiAgentDispatcher(llm_backend=backend)

# 使用流式 Worker
from scripts.collaboration.worker import Worker
worker = Worker(role="architect", backend=backend, stream=True)
# Worker 会实时打印 LLM 响应块

result = disp.dispatch("设计认证系统", roles=["architect"])
disp.shutdown()
```

### 使用配置管理器

```python
# ConfigManager removed in V3.7.2 (dead code)

config_mgr = ConfigManager()
config = config_mgr.load()
print(f"Backend: {config.backend}")
print(f"Model: {config.model}")
print(f"Timeout: {config.timeout}")
```

### 使用检查点管理器

```python
from scripts.collaboration.checkpoint_manager import CheckpointManager

ckpt_mgr = CheckpointManager(storage_dir="/tmp/checkpoints")

# 从调度结果创建检查点
checkpoint = ckpt_mgr.create_checkpoint_from_dispatch(dispatch_result)

# 列出所有检查点
checkpoints = ckpt_mgr.list_checkpoints()

# 从检查点恢复
restored = ckpt_mgr.load_checkpoint(checkpoint.checkpoint_id)
```

## 角色参考

| 角色 | CLI ID | 别名 | 最适合 |
|------|--------|------|--------|
| 架构师 | `arch` | `architect` | 系统设计、技术选型、性能/安全/数据架构 |
| 产品经理 | `pm` | `product-manager` | 需求分析、用户故事、验收标准 |
| 安全专家 | `sec` | `security` | 威胁建模、漏洞审计、合规检查 |
| 测试专家 | `test` | `tester`, `qa` | 测试策略、质量保证、边界用例 |
| 编码员 | `coder` | `solo-coder`, `dev` | 功能实现、代码审查、性能优化 |
| 运维工程师 | `infra` | `devops` | CI/CD、容器化、监控、基础设施 |
| UI 设计师 | `ui` | `ui-designer` | UX 流程、交互设计、无障碍 |

## CLI 选项

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--task`, `-t` | string | 必填 | 任务描述 |
| `--roles`, `-r` | list | auto | 角色（短 ID: arch/pm/test/coder/ui/infra/sec） |
| `--mode`, `-m` | enum | auto | 执行模式: auto/parallel/sequential/consensus |
| `--backend`, `-b` | enum | mock | LLM 后端: mock/trae/openai/anthropic |
| `--base-url` | string | env | 自定义 API 地址（或 OPENAI_BASE_URL 环境变量） |
| `--model` | string | env | 模型名（或 OPENAI_MODEL/ANTHROPIC_MODEL 环境变量） |
| `--stream` | flag | false | 实时流式输出 LLM 响应（需 --backend） |
| `--format`, `-f` | enum | markdown | 输出: markdown/json/compact/structured/detailed |
| `--dry-run` | flag | false | 模拟不执行 |
| `--quick`, `-q` | flag | false | 使用 quick_dispatch（3 种格式） |
| `--action-items` | flag | false | 包含 H/M/L 优先级行动项 |
| `--timing` | flag | false | 包含执行时间数据 |
| `--persist-dir` | string | auto | 自定义 scratchpad 目录 |
| `--no-warmup` | flag | false | 禁用启动预热 |
| `--no-compression` | flag | false | 禁用上下文压缩 |
| `--skip-permission` | flag | false | 跳过权限检查 |
| `--no-memory` | flag | false | 禁用记忆桥接 |
| `--no-skillify` | flag | false | 禁用技能学习 |
| `--permission-level` | enum | DEFAULT | PLAN/DEFAULT/AUTO/BYPASS |

## 环境变量

| 变量 | 说明 | 必需 |
|------|------|------|
| `OPENAI_API_KEY` | OpenAI 兼容后端的 API Key | `--backend openai` 时必需 |
| `OPENAI_BASE_URL` | 自定义 API 端点（如 `https://api.moka-ai.com/v1`） | 可选 |
| `OPENAI_MODEL` | 模型名（如 `gpt-4`, `moka/claude-sonnet-4-6`） | 可选 |
| `ANTHROPIC_API_KEY` | Anthropic Claude 的 API Key | `--backend anthropic` 时必需 |
| `ANTHROPIC_MODEL` | 模型名（如 `claude-sonnet-4-20250514`） | 可选 |
| `DEVSQUAD_LLM_BACKEND` | 默认后端（mock/openai/anthropic） | 可选 |
| `DEVSQUAD_LOG_LEVEL` | 日志级别 | 可选 |

## V4.4.0 新模块示例

V4.4.0 引入 5 个增强模块（RiskRegister / ViewpointRegistry / ErrorBudgetTracker / GapAnalyzer / DoraMetricsCollector），覆盖 PMP 风险管理、TOGAF 视点正交性、SRE 错误预算、架构差距分析与 DORA 指标 5 个维度。全部 mock 模式可运行，无需 API key。每个模块内置模块级 `_call_counter` 反幽灵计数器，dispatch pipeline 自动激活并由 E2E 测试验证。

### 示例 7：RiskRegister — 风险注册与评估

PMP 风险管理：记录 probability × impact，支持 7 角色加权投票，输出 Markdown "Risk Management" 章节。

```bash
python3 -c "
from scripts.collaboration.risk_register import RiskRegister
rr = RiskRegister()
# add() 返回 RiskItem，id 由 description 哈希自动生成（R-<sha256[:12]>）
r1 = rr.add(description='API rate limit exceeded', probability=0.7, impact=0.5)
r2 = rr.add(description='Database connection pool exhaustion', probability=0.3, impact=0.8)
# 7-role weighted voting: role_id -> (probability, impact)
rr.assess(r1.id, votes={'architect': (0.7, 0.5), 'security': (0.6, 0.6)})
print(rr.export_markdown())
"
```

预期输出（验证于 2026-07-30, V4.4.1, backend=mock）：
```
## Risk Management

| ID | Description | Probability | Impact | Exposure | Strategy | Owner | Category |
|---|---|---|---|---|---|---|---|
| R-2fab1aedbad8 | API rate limit exceeded | 0.65 | 0.55 | 0.3570 | accept |  | general |
| R-36849b6da8a4 | Database connection pool exhaustion | 0.30 | 0.80 | 0.2400 | accept |  | general |
```

### 示例 8：ViewpointRegistry — 视点正交性检查

TOGAF 视点注册：7 角色绑定正式视点，`is_orthogonal()` 判断两角色视点是否无共享 concerns，供 ConsensusEngine 仲裁 SPLIT。

```bash
python3 -c "
from scripts.collaboration.viewpoint_registry import ViewpointRegistry
vr = ViewpointRegistry()
# 架构师（functional+data）vs 安全专家（threat）—— 无共享 concerns，正交
print('architect vs security orthogonal:', vr.is_orthogonal('architect', 'security'))
# 架构师 vs 开发者（implementation）—— 共享 'interface'，部分重叠
print('architect vs solo-coder orthogonal:', vr.is_orthogonal('architect', 'solo-coder'))
"
```

预期输出（验证于 2026-07-30, V4.4.1, backend=mock）：
```
architect vs security orthogonal: True
architect vs solo-coder orthogonal: False
```

### 示例 9：ErrorBudgetTracker — SLO 错误预算

SRE 错误预算：按 SLO 目标与滚动窗口计算预算消耗，P10 部署门控当预算耗尽时阻断。

```bash
python3 -c "
from scripts.collaboration.error_budget_tracker import ErrorBudgetTracker
eb = ErrorBudgetTracker(slo_target=0.999, window_days=30)
# 模拟 30 天窗口 10000 次请求中 1 次错误
result = eb.calculate(slo_target=0.999, window_days=30, observed_errors=1, total_events=10000)
print(f'Status: {result.status.value.upper()}')
print(f'Remaining budget: {result.budget_remaining:.4f}')
print(f'Burn rate: {result.burn_rate:.2f}x')
"
```

预期输出（验证于 2026-07-30, V4.4.1, backend=mock）：
```
Status: HEALTHY
Remaining budget: 0.9000
Burn rate: 0.10x
```

### 示例 10：GapAnalyzer — 架构差距分析

TOGAF 差距分析：对比 current/target 架构生成 Gap 列表，按优先级排序并输出 Markdown 路线图。

```bash
python3 -c "
from scripts.collaboration.gap_analyzer import GapAnalyzer
ga = GapAnalyzer()
gaps = ga.analyze(
    current={'auth': 'basic', 'monitoring': 'none', 'logging': 'file'},
    target={'auth': 'oauth2', 'monitoring': 'prometheus', 'logging': 'elk'}
)
prioritized = ga.prioritize(gaps)
print(ga.generate_roadmap(prioritized))
"
```

预期输出（验证于 2026-07-30, V4.4.1, backend=mock）：
```
## Gap Analysis Roadmap

| Phase | Gap | Priority | Effort |
|---|---|---|---|
| Phase 1 | Migrate auth from basic to oauth2 | medium | 5.0 |
| Phase 2 | Migrate monitoring from none to prometheus | medium | 5.0 |
| Phase 3 | Migrate logging from file to elk | medium | 5.0 |
```

### 示例 11：DoraMetricsCollector — DORA 指标收集

DORA 4 指标（部署频率 / Lead Time / 变更失败率 / MTTR）：从 dispatch 审计日志收集，P11 门控当变更失败率 > 15% 时阻断。

```bash
python3 -c "
from scripts.collaboration.dora_metrics_collector import DoraMetricsCollector
dora = DoraMetricsCollector()
# 模拟 30 天内 10 次部署，1 次失败
records = [{'timestamp': '2026-07-30T10:00:00Z', 'success': True, 'duration': 300}] * 9 + [{'timestamp': '2026-07-29T14:00:00Z', 'success': False, 'duration': 600}]
metrics = dora.collect_from_dispatch(records, window_days=30)
metric_name = 'change_failure_rate'
print(f'Deployment Frequency: {metrics.deployment_frequency:.2f}/day')
print(f'Lead Time: {metrics.lead_time:.1f}h')
print(f'Change Failure Rate: {metrics.change_failure_rate:.1%}')
print(f'MTTR: {metrics.mttr:.1f}h')
print(f'CFR Rating: {metrics.rating(metric_name)}')
"
```

预期输出（验证于 2026-07-30, V4.4.1, backend=mock）：
```
Deployment Frequency: 0.33/day
Lead Time: 2.0h
Change Failure Rate: 10.0%
MTTR: 2.0h
CFR Rating: high
```

### 防幽灵功能验证

所有 5 个 V4.4.0 模块在 dispatch pipeline 中自动激活。E2E 测试 `test_v440_anti_ghost.py` 验证每个模块的 `_call_counter > 0`：

```bash
# 运行防幽灵 E2E 测试
pytest tests/e2e/test_v440_anti_ghost.py -v
# 预期：1 passed, 5 modules all activated
```

详见 [GUIDE.md §18. V4.4.0 新增模块](GUIDE.md#18-v440-新增模块) 完整功能说明。

## MCP 服务器（用于 OpenClaw / Cursor）

```bash
# 安装 MCP 包（可选）
pip install mcp

# stdio 模式启动
python3 scripts/mcp_server.py

# SSE 模式启动
python3 scripts/mcp_server.py --port 8080
```

暴露 6 个工具: `multiagent_dispatch`, `multiagent_quick`, `multiagent_roles`,
`multiagent_status`, `multiagent_analyze`, `multiagent_shutdown`。
