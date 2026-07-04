# DevSquad V3.9.2 路线图实施计划

**文档版本**: 1.0.0  
**规划日期**: 2026-06-25  
**依据文档**:
- [docs/_archive/assessments/LOOP_ENGINEERING_IMPLEMENTATION_ASSESSMENT.md](../_archive/assessments/LOOP_ENGINEERING_IMPLEMENTATION_ASSESSMENT.md)
- [docs/MATURITY_ASSESSMENT.md](../MATURITY_ASSESSMENT.md)
- 《Loop Engineering 橙皮书 v260615》
- DevSquad SKILL.md Cybernetics Enhancement (V3.6.5)

---

## 1. 目标

推进 V3.9 路线图剩余 4 项核心工作，并响应新增需求：

1. **LLM 回退策略**: DevSquad 被调用时优先尝试真实 LLM，失败后再回退到 Mock
2. **巨型文件拆分**: 42 个 >500 行文件，从 `dashboard.py` (1087 行) 开始
3. **真实 LLM 后端集成测试**: 补充真实模型调用测试
4. **审计日志持久化**: 从内存持久化到文件/DB
5. **P3 清理**: 魔法数字提取 + 宽泛异常收窄（顺手做）

---

## 2. 实施顺序与优先级

| # | 任务 | 优先级 | 依赖 | 预计影响范围 | 是否阻塞发布 |
|---|---|---|---|---|---|
| 1 | LLM fallback 优先真实模型 | P1 | 无 | `llm_backend.py`, `async_llm_backend.py`, `cli_utils.py`, `config/deployment.yaml` | 否 |
| 2 | 巨型文件拆分 (dashboard.py) | P1 | 无 | `dashboard.py` → 新模块包 | 否 |
| 3 | 真实 LLM 后端集成测试 | P1 | 任务 1 | `tests/integration/test_real_llm.py` | 否 |
| 4 | 审计日志持久化 | P2 | 无 | `scripts/collaboration/audit_logger.py`, `scripts/api/security.py` | 否 |
| 5 | P3 清理 | P3 | 无 | 多个文件的小范围修改 | 否 |

---

## 3. 任务 1: LLM Fallback 优先真实模型

### 3.1 现状

- 默认后端是 `mock`
- 已有 `FallbackBackend` 组件，但默认不启用
- 真实 LLM 需要显式配置 `DEVSQUAD_LLM_BACKEND=openai/anthropic/fallback`

### 3.2 目标行为

```
用户无显式配置时:
  若存在真实 API key → 优先尝试真实 LLM
  若真实 LLM 失败   → 自动回退到 Mock
  若无 API key      → 直接使用 Mock (保持现有行为)

用户显式配置 mock 时:
  仍然使用 Mock (向后兼容)
```

### 3.3 设计

新增后端类型 `"auto"`：

```python
def create_backend(backend_type="auto", ...):
    if backend_type in (None, "", "auto"):
        # 1. 检测可用真实后端
        # 2. 构建 FallbackBackend([real_backend, MockBackend()])
        # 3. 无 key 时返回 MockBackend()
```

- 不改变 `mock`/`openai`/`anthropic`/`trae` 的显式行为
- 默认 `DEVSQUAD_LLM_BACKEND` 从 `"mock"` 改为 `"auto"`
- CLI `--backend` choices 增加 `"auto"`
- 配置文件中 `llm.default_backend` 默认值同步更新

### 3.4 需要修改的文件

1. `scripts/collaboration/llm_backend.py` — `create_backend()` 默认分支
2. `scripts/collaboration/async_llm_backend.py` — `AsyncLLMBackendFactory.create()` 默认分支
3. `scripts/cli_utils.py` — `BACKENDS` 列表、`_create_backend()`
4. `scripts/cli.py` — `--backend` 参数默认值
5. `config/deployment.yaml` — `llm.default_backend`
6. `.env.example` — 新增说明
7. `README.md` / `README-CN.md` / `SKILL.md` — 更新默认行为描述

### 3.5 测试策略

- 单元测试:
  - 无 key 时 `create_backend("auto")` 返回 `MockBackend`
  - 有 key 时 `create_backend("auto")` 返回 `FallbackBackend`，链首为真实后端
  - 真实后端抛异常时自动切换到 Mock
- 集成测试:
  - 显式 `--backend mock` 仍输出 mock
  - 显式 `--backend openai` with key 调用真实模型
- E2E 测试:
  - `DEVSQUAD_LLM_BACKEND=mock` 保持现有行为

---

## 4. 任务 2: 巨型文件拆分

### 4.1 现状

- 42 个文件 >500 行
- 最大文件 `scripts/dashboard.py` (1087 行)
- 技术债已记录在 [docs/MATURITY_ASSESSMENT.md](../MATURITY_ASSESSMENT.md)

### 4.2 拆分原则

1. **单一职责**: 每个模块只做一件事
2. **向后兼容**: 保留原 `dashboard.py` 作为 facade，导入新模块
3. **不破坏现有导入**: 外部 `from scripts.dashboard import X` 继续工作
4. **测试同步迁移**: 测试文件按新模块组织

### 4.3 dashboard.py 拆分方案

```
scripts/dashboard/
├── __init__.py          # 重新导出原 dashboard.py 的 public API
├── app.py               # Streamlit app 入口（原 dashboard.py 的 main 逻辑）
├── auth_views.py        # 登录/登出/会话管理视图
├── metrics_views.py     # 指标展示视图
├── lifecycle_views.py   # 生命周期视图
├── dispatch_views.py    # 调度任务视图
├── components.py        # 可复用 UI 组件
└── state.py             # session_state 管理
```

### 4.4 其他候选文件（后续批次）

| 文件 | 行数 | 拆分方向 |
|---|---|---|
| `scripts/collaboration/dispatcher.py` | ~730 | 拆出 pipeline 协调器 |
| `scripts/collaboration/coordinator.py` | ~620 | 拆出 worker 管理、briefing 链 |
| `scripts/collaboration/dispatch_steps.py` | ~1100 | 拆出 PreDispatchPipeline / PostDispatchPipeline |
| `scripts/collaboration/memory_bridge.py` | ~580 | 拆出 memory types、query、serializer |

本版本优先完成 `dashboard.py`。

---

## 5. 任务 3: 真实 LLM 后端集成测试

### 5.1 现状

- 已有 `tests/integration/test_real_llm.py` 和 `tests/smoke/test_real_llm_smoke.py`
- 大部分 CI 测试使用 mock
- 真实 LLM 测试需要 API key，通常标记为 slow 或 integration

### 5.2 目标

- 为新的 `"auto"` fallback 模式编写集成测试
- 确保真实后端失败时优雅降级到 mock
- 添加可重复运行的 smoke 测试（默认跳过，CI 不跑）

### 5.3 测试文件

- `tests/integration/test_llm_auto_fallback.py`
- `tests/smoke/test_real_llm_auto_mode.py`（标记 `@pytest.mark.slow`）

### 5.4 关键测试用例

1. `test_auto_with_key_uses_real_backend`: 有 key 时优先真实
2. `test_auto_without_key_uses_mock`: 无 key 时直接 mock
3. `test_auto_fallback_when_real_fails`: 真实失败时降级 mock
4. `test_explicit_mock_stays_mock`: 显式 mock 保持 mock
5. `test_explicit_openai_stays_openai`: 显式 openai 不 fallback

---

## 6. 任务 4: 审计日志持久化

### 6.1 现状

- `AuditLogger` 使用内存中 CSV/JSON 缓冲
- REST API security 中的 `audit_log()` 调用 `AuditLogger`
- 日志在进程退出后丢失

### 6.2 目标

- 默认持久化到本地文件（`logs/audit/audit_YYYY-MM-DD.csv`）
- 可选持久化到 SQLite（配置驱动）
- 保持内存缓冲作为写入缓存
- 提供查询接口（按时间、用户、动作过滤）

### 6.3 设计

```python
class AuditLogger:
    def __init__(self, storage="file", path="logs/audit", db_url=None):
        ...

    def log(self, ...):
        # 1. 生成 entry + hash chain
        # 2. 写入内存缓冲
        # 3. 异步/同步 flush 到 file/db
```

### 6.4 需要修改的文件

1. `scripts/collaboration/audit_logger.py` — 核心持久化逻辑
2. `scripts/api/security.py` — `get_audit_logger()` 读取配置
3. `config/deployment.yaml` — 新增 `audit_logger` 配置段
4. `tests/test_audit_logger.py` — 持久化测试

---

## 7. 任务 5: P3 清理（已完成）

### 7.1 魔法数字

- [x] 提取 `llm_backend.py` / `async_llm_backend.py` 中重复出现的默认值：
  - `DEFAULT_TIMEOUT = 120.0`
  - `DEFAULT_MAX_TOKENS = 4096`
  - `DEFAULT_TEMPERATURE = 0.7`
  - `DEFAULT_COOLDOWN_SECONDS = 30.0`
  - `DEFAULT_BACKOFF_BASE = 2`
  - `DEFAULT_MAX_RETRIES = 3`
  - `DEFAULT_MODEL_OPENAI = "gpt-4"`
  - `DEFAULT_MODEL_ANTHROPIC = "claude-sonnet-4-20250514"`
  - `MOCK_SEPARATOR_WIDTH = 50`
  - `async_llm_backend.py` 本地保留 `DEFAULT_MAX_CONCURRENCY = 10`
- [x] `async_llm_backend.py` 复用 `llm_backend.py` 的共享常量，避免二义性

### 7.2 宽泛异常

- [x] 将 `generate()` / `is_available()` 中的 `(ConnectionError, TimeoutError, OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError)` 收窄为：
  - 重试异常：网络异常 + 对应厂商 `APIError`（`openai.APIError` / `anthropic.APIError`）
  - 可用性检查：`ImportError, ConnectionError, TimeoutError, OSError, RuntimeError`
- [x] `FallbackBackend` / `AsyncFallbackBackend` 使用 `_get_fallback_exceptions()` 统一处理真实后端故障
- [x] Prometheus 指标记录的兜底异常收窄为 `(RuntimeError, ValueError, AttributeError)`，并注明“optional metrics must never break LLM calls”

### 7.3 验证

- [x] `tests/test_llm_auto_fallback.py` 全绿
- [x] `python -m mypy scripts/collaboration/llm_backend.py scripts/collaboration/async_llm_backend.py` 0 errors
- [x] 全量单元测试 2703 passed

---

## 8. E2E 测试计划

发布前必须完成模拟真实用户使用的 E2E 测试：

| 场景 | 命令/动作 | 验证点 |
|---|---|---|
| 服务启动 | `scripts/start.sh` | 健康检查 200 |
| 登录 | Streamlit 登录页 | admin 登录成功 |
| 记录交流 | 提交任务 dispatch | 返回 DispatchResponse |
| 预定日程 | lifecycle phase advance | phase 状态更新 |
| 仪表盘 | 访问 Streamlit dashboard | 指标显示正常 |
| 承诺履约 | feedback loop auto-retry | quality >= 0.5 |
| 数据导出 | audit log 导出 CSV | 文件存在且非空 |

---

## 9. 文档同步清单

每完成一项任务，必须同步更新：

- [ ] `README.md` / `README-CN.md`
- [ ] `SKILL.md`
- [ ] `CHANGELOG.md` / `CHANGELOG-CN.md`
- [ ] `docs/MATURITY_ASSESSMENT.md`（技术债状态）
- [ ] `docs/PROJECT_STATUS.md`（若存在）
- [ ] `docs/spec/` 下相关设计文档
- [ ] `.env.example`

---

## 10. Git 工作流

每个任务独立 PR：

1. `feat/llm-auto-fallback`
2. `refactor/split-dashboard`
3. `test/real-llm-integration`
4. `feat/audit-log-persistence`
5. `cleanup/p3-magic-numbers`

禁止直接 push 到 main，所有 PR 必须通过 CI 后由 review 合并。

---

## 11. 验收标准

V3.9.2 完成时：

- [ ] `DEVSQUAD_LLM_BACKEND=auto` 时，有 key 优先真实 LLM，失败自动 mock
- [ ] `dashboard.py` 拆分完成，原导入路径兼容
- [ ] 新增真实 LLM fallback 集成测试，标记 slow
- [ ] `AuditLogger` 默认持久化到文件
- [ ] CI 全绿：test / lint / security / build
- [ ] mypy 0 errors
- [ ] E2E 测试通过
- [ ] 所有相关文档同步更新
