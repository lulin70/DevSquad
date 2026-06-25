# REST API 安全集成设计文档

> **文档类型**: 技术设计文档
> **版本**: V1.0
> **关联 Issue**: [#4](https://github.com/lulin70/DevSquad/issues/4)
> **创建日期**: 2026-06-24
> **状态**: Draft

---

## 1. 背景与目标

### 1.1 问题

DevSquad REST API (`scripts/api_server.py`) 有 **15 个端点**，全部为零安全防护：

| 路由文件 | 端点数 | 认证 | 输入验证 | RBAC | 审计 |
|----------|--------|------|----------|------|------|
| dispatch.py | 4 | ❌ | ❌ | ❌ | ❌ |
| lifecycle.py | 5 | ❌ | ❌ | ❌ | ❌ |
| metrics.py | 1 | ❌ | N/A | ❌ | ❌ |
| metrics_gates.py | 5 | ❌ | N/A | ❌ | ❌ |

安全模块已实现且有单元测试，但未接入 API 层：
- `InputValidator`（359行，53个检测模式）
- `RBACEngine`（733行，5级角色×15个权限）
- `AuditLogger`（895行，SHA256防篡改链）
- `AuthManager`（485行，但耦合 Streamlit，不可直接用于 FastAPI）

### 1.2 目标

1. 所有写操作端点要求 API Key 认证
2. 任务调度端点集成 InputValidator 防注入
3. 每个端点通过 RBAC 校验权限
4. 所有写操作记录审计日志
5. 读操作端点（health/metrics）可选认证

### 1.3 非目标

- 不实现 JWT/OAuth2（API Key 足够，保持简单）
- 不重构 AuthManager（Streamlit 耦合留待后续）
- 不实现速率限制（独立 PR 处理）

---

## 2. 设计决策

### 2.1 认证方案：API Key

**选择**: `X-API-Key` Header 携带 API Key

**理由**:
- 最简方案，无状态，无需 session 管理
- 与 RBACEngine 自然映射（API Key → user_id → roles → permissions）
- 适合服务间调用和程序化访问
- 可存储在 `config/deployment.yaml`

**格式**: `dsk_<32hex>`（如 `dsk_a1b2c3d4e5f6...`）

**存储**: SHA-256 哈希存储在配置文件，明文仅在创建时展示一次

### 2.2 权限映射

| 端点 | 方法 | 所需权限 | 角色要求 |
|------|------|----------|----------|
| `/api/v1/tasks/dispatch` | POST | `TASK_EXECUTE` | OPERATOR+ |
| `/api/v1/tasks/quick` | POST | `TASK_EXECUTE` | OPERATOR+ |
| `/api/v1/tasks/history` | GET | `TASK_READ` | VIEWER+ |
| `/api/v1/roles` | GET | `TASK_READ` | VIEWER+ |
| `/api/v1/lifecycle/phases` | GET | `TASK_READ` | VIEWER+ |
| `/api/v1/lifecycle/phases/{id}` | GET | `TASK_READ` | VIEWER+ |
| `/api/v1/lifecycle/status` | GET | `TASK_READ` | VIEWER+ |
| `/api/v1/lifecycle/actions` | POST | `TASK_UPDATE` | OPERATOR+ |
| `/api/v1/lifecycle/mappings` | GET | `TASK_READ` | VIEWER+ |
| `/api/v1/metrics/current` | GET | `CONFIG_READ` | ANALYST+ |
| `/api/v1/metrics/history` | GET | `CONFIG_READ` | ANALYST+ |
| `/api/v1/gates/status` | GET | `TASK_READ` | VIEWER+ |
| `/api/v1/gates/check` | POST | `TASK_UPDATE` | OPERATOR+ |
| `/api/v1/health` | GET | 无（公开） | 无 |
| `/metrics` | GET | `AUDIT_READ` | ANALYST+ |

### 2.3 开发模式

通过环境变量 `DEVSQUAD_API_AUTH_DISABLED=1` 可禁用认证（仅开发/测试环境）。

---

## 3. 架构设计

### 3.1 新增文件

```
scripts/api/
├── security.py          # API Key 认证 + RBAC 依赖注入
└── routes/
    └── (现有路由文件修改)
```

### 3.2 security.py 核心组件

```python
# 1. API Key 存储（从 config/deployment.yaml 加载）
class APIKeyStore:
    """管理 API Key 到 user_id 的映射"""
    def verify(self, api_key: str) -> str | None  # 返回 user_id 或 None

# 2. FastAPI 依赖：认证
async def require_api_key(request: Request) -> str:
    """从 X-API-Key header 提取并验证，返回 user_id"""
    # 开发模式跳过
    # 缺失/无效返回 401

# 3. FastAPI 依赖：权限检查
def require_permission(permission: Permission):
    """返回依赖函数，校验 user_id 是否有指定权限"""
    async def dependency(user_id: str = Depends(require_api_key)) -> str:
        # RBACEngine.check_permission(user_id, permission)
        # 失败返回 403
        return user_id
    return dependency

# 4. AuditLogger 单例
_audit_logger: AuditLogger | None = None
def get_audit_logger() -> AuditLogger | None
```

### 3.3 路由集成模式

```python
# dispatch.py — 写操作端点
@router.post("/dispatch")
async def dispatch_task(
    request: TaskDispatchRequest,
    user_id: str = Depends(require_permission(Permission.TASK_EXECUTE)),
):
    # 1. InputValidator 验证 task 和 roles
    validation = InputValidator().validate_task(request.task)
    if not validation.valid:
        raise HTTPException(422, detail=validation.reason)

    # 2. 执行调度
    result = _get_dispatcher().dispatch(...)

    # 3. 审计日志
    get_audit_logger()?.log(
        user_id=user_id, action="task:dispatch",
        resource_type="task", resource_id=result.task_id,
        result="success"
    )
    return _convert_dispatch_result(result)
```

```python
# lifecycle.py — 读操作端点
@router.get("/phases")
async def list_phases(
    user_id: str = Depends(require_permission(Permission.TASK_READ)),
):
    ...
```

```python
# metrics_gates.py — 健康检查（公开）
@router.get("/health")
async def health_check():
    # 无 Depends，公开访问
    ...
```

---

## 4. 实施计划

### Stage 1: 认证基础设施 + InputValidator（本次 PR）

1. 创建 `scripts/api/security.py`：
   - `APIKeyStore` — 从 `config/deployment.yaml` 加载 API Key
   - `require_api_key` 依赖
   - `require_permission` 依赖工厂
   - `get_audit_logger` 单例

2. 修改 `scripts/api/routes/dispatch.py`：
   - `dispatch_task` 和 `quick_dispatch` 添加 `Depends(require_permission(Permission.TASK_EXECUTE))`
   - 集成 `InputValidator.validate_task()` 和 `validate_roles()`
   - 添加审计日志

3. 修改 `scripts/api/routes/lifecycle.py`：
   - 读端点添加 `Depends(require_permission(Permission.TASK_READ))`
   - `execute_phase_action` 添加 `Depends(require_permission(Permission.TASK_UPDATE))`
   - 添加审计日志

4. 修改 `scripts/api/routes/metrics_gates.py`：
   - 读端点添加 `Depends(require_permission(Permission.TASK_READ/CONFIG_READ))`
   - `check_specific_gate` 添加 `Depends(require_permission(Permission.TASK_UPDATE))`
   - `health_check` 保持公开

5. 修改 `scripts/api/routes/metrics.py`：
   - `/metrics` 添加 `Depends(require_permission(Permission.AUDIT_READ))`

### Stage 2: 安全集成测试（本次 PR）

1. 未授权请求返回 401
2. 权限不足返回 403
3. 有效 API Key + 正确权限 → 200
4. InputValidator 拒绝注入 payload → 422
5. 审计日志记录写操作
6. 开发模式（`DEVSQUAD_API_AUTH_DISABLED=1`）跳过认证

### Stage 3: 配置与文档（本次 PR）

1. `config/deployment.yaml` 添加 `api_keys` 配置段
2. 更新 `api_server.py` 启动日志显示安全状态
3. 更新 Issue #4 关闭条件

---

## 5. 配置格式

### 5.1 config/deployment.yaml 新增

```yaml
api_security:
  enabled: true  # 设为 false 禁用所有安全检查
  api_keys:
    - key_hash: "sha256:a1b2c3d4..."  # SHA-256 哈希
      user_id: "admin@example.com"
      roles: ["SUPER_ADMIN"]
      active: true
    - key_hash: "sha256:e5f6g7h8..."
      user_id: "operator@example.com"
      roles: ["OPERATOR"]
      active: true
```

### 5.2 API Key 生成

```bash
# 生成新 API Key
python -c "import secrets; key = 'dsk_' + secrets.token_hex(16); print(f'API Key: {key}'); import hashlib; print(f'SHA-256: sha256:{hashlib.sha256(key.encode()).hexdigest()}')"
```

---

## 6. 测试策略

### 6.1 测试维度

| 维度 | 测试内容 | 数量目标 |
|------|----------|----------|
| 认证 | 无 Key/无效 Key/有效 Key | 3+ |
| 授权 | 权限不足/权限充足 | 4+ |
| 输入验证 | SQL注入/Prompt注入/XSS/正常输入 | 5+ |
| 审计日志 | 写操作记录/读操作不记录 | 2+ |
| 开发模式 | AUTH_DISABLED 跳过 | 1+ |
| 边界 | 空 Key/超长 Key/格式错误 | 3+ |

### 6.2 测试文件

`tests/test_api_security.py` — 新建，覆盖所有安全场景

---

## 7. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 现有 API 调用方因认证失效 | 开发模式 `DEVSQUAD_API_AUTH_DISABLED=1` 兼容 |
| API Key 泄露 | SHA-256 哈希存储，明文仅展示一次 |
| RBACEngine 内存状态丢失 | 配置文件持久化，启动时加载 |
| AuditLogger 性能影响 | 异步缓冲写入，不阻塞请求 |

---

## 8. 验收标准

- [ ] 所有写操作端点要求 API Key 认证
- [ ] 任务调度端点集成 InputValidator
- [ ] 每个端点通过 RBAC 校验权限
- [ ] 写操作记录审计日志
- [ ] health 端点保持公开
- [ ] 开发模式可禁用认证
- [ ] 安全集成测试全部通过
- [ ] 现有 API 测试在 AUTH_DISABLED=1 下仍通过
- [ ] CI 全部通过
