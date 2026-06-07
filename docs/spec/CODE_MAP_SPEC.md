# 代码地图生成器 (Code Map Generator)

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

## 输出格式

### Markdown 代码地图结构

```markdown
# {项目名称} 代码地图

> 生成时间: {时间戳}
> 代码版本: {git commit hash}
> 分析文件数: {文件数量}

## 项目概览

- **项目名称**: {名称}
- **项目路径**: {路径}
- **技术栈**: {语言, 框架列表}
- **代码规模**: {简单/中等/复杂/超大型}
- **架构风格**: {分层/Clean/Hexagonal等}

## 架构分层

### 1. API Layer (接口层)
**职责**: 处理 HTTP 请求、路由分发、参数验证

**文件列表**:
| 文件 | 职责 | 复杂度 |
|------|------|--------|
| `api/user.go` | 用户相关 API 处理 | 中 |

**关键接口**:
- `POST /api/users` - 创建用户
- `GET /api/users/{id}` - 获取用户信息

### 2. Service Layer (业务层)
**职责**: 实现核心业务逻辑、事务管理

**文件列表**:
| 文件 | 职责 | 复杂度 |
|------|------|--------|
| `service/user_service.go` | 用户业务逻辑 | 高 |

**核心函数**:
- `CreateUser(ctx, req)` - 创建用户业务逻辑
  - 流程: 参数验证 → 检查重复 → 加密密码 → 存储 → 发送通知
  - 调用: `repository.CreateUser()`, `password.Encrypt()`, `notification.Send()`

### 3. Data Layer (数据层)
**职责**: 数据持久化、数据库访问

**文件列表**:
| 文件 | 职责 | 复杂度 |
|------|------|--------|
| `repository/user_repo.go` | 用户数据访问 | 低 |

## 模块详解

### module: user

**路径**: `src/user/`

**功能说明**:
用户管理模块，负责用户的注册、登录、信息修改等全部用户相关功能。

**包含文件**:
- `api/user.go` - API 端点定义
- `service/user_service.go` - 业务逻辑
- `repository/user_repo.go` - 数据访问
- `model/user.go` - 数据模型
- `util/password.go` - 密码工具

**导出接口**:
```go
// 创建用户
func CreateUser(ctx context.Context, req *CreateUserRequest) (*User, error)

// 用户登录
func Login(ctx context.Context, req *LoginRequest) (*LoginResponse, error)

// 获取用户信息
func GetUser(ctx context.Context, id string) (*User, error)
```

**内部调用**:
```
CreateUser
├── validator.Validate(req)     # 参数验证
├── password.Encrypt(req.Password)  # 密码加密
├── repository.CreateUser()     # 数据存储
└── notification.Send()         # 发送通知
```

**依赖模块**:
- `module: auth` - 认证模块
- `module: notification` - 通知模块

## 文件详情

### file:src/user/service/user_service.go

**文件路径**: `src/user/service/user_service.go`

**功能描述**:
用户业务逻辑层，负责处理用户相关的核心业务逻辑，包括用户注册、登录、信息修改、密码重置等功能。该服务是用户管理模块的核心，协调数据访问层和外部服务。

**代码行数**: 245 行

**复杂度**: 高

**主要函数**:

#### func: CreateUser
```go
func CreateUser(ctx context.Context, req *CreateUserRequest) (*User, error)
```

**功能**: 创建新用户

**流程**:
1. 参数验证 (validator.Validate)
2. 检查用户名是否已存在 (repository.ExistsByUsername)
3. 检查邮箱是否已存在 (repository.ExistsByEmail)
4. 密码强度验证 (password.CheckStrength)
5. 密码加密 (password.Encrypt)
6. 创建用户记录 (repository.Create)
7. 发送欢迎邮件 (notification.SendWelcomeEmail)

**调用关系**:
```
CreateUser
├── validator.Validate
├── repository.ExistsByUsername
├── repository.ExistsByEmail
├── password.CheckStrength
├── password.Encrypt
├── repository.Create
└── notification.SendWelcomeEmail
```

**输入**:
```go
type CreateUserRequest struct {
    Username string  // 用户名，3-20字符
    Email    string  // 邮箱，唯一
    Password string  // 密码，最少8字符
    Nickname string  // 昵称，可选
}
```

**输出**:
```go
type User struct {
    ID       string  // 用户ID
    Username string  // 用户名
    Email    string  // 邮箱
    Nickname string  // 昵称
    CreatedAt time.Time  // 创建时间
}
```

**错误处理**:
- `ErrInvalidUsername` - 用户名格式错误
- `ErrInvalidEmail` - 邮箱格式错误
- `ErrWeakPassword` - 密码强度不足
- `ErrUsernameExists` - 用户名已存在
- `ErrEmailExists` - 邮箱已存在

#### func: Login
```go
func Login(ctx context.Context, req *LoginRequest) (*LoginResponse, error)
```

**功能**: 用户登录

**流程**:
1. 参数验证
2. 根据用户名查询用户 (repository.FindByUsername)
3. 验证密码 (password.Verify)
4. 生成访问令牌 (auth.GenerateToken)
5. 更新最后登录时间 (repository.UpdateLastLogin)
6. 返回登录响应

**调用关系**:
```
Login
├── validator.Validate
├── repository.FindByUsername
├── password.Verify
├── auth.GenerateToken
└── repository.UpdateLastLogin
```

## 配置文件

### config:config/application.yaml

**文件路径**: `config/application.yaml`

**配置内容**:
```yaml
server:
  port: 8080
  host: "0.0.0.0"

database:
  type: mysql
  host: "localhost"
  port: 3306
  name: "app_db"
  username: "root"
  password: "${DB_PASSWORD}"

redis:
  host: "localhost"
  port: 6379
  password: "${REDIS_PASSWORD}"
  db: 0

jwt:
  secret: "${JWT_SECRET}"
  expiration: 86400  # 24小时
```

**配置说明**:
| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| server.port | HTTP 服务端口 | 8080 |
| database.type | 数据库类型 | mysql |
| jwt.expiration | Token 过期时间(秒) | 86400 |

## 调用流程图

### 用户注册流程

```
Client
  │
  ▼
API Layer: POST /api/users
  │
  ▼
┌─────────────────────────────────────┐
│ Service Layer: CreateUser          │
│                                     │
│  1. validator.Validate              │
│  2. repository.ExistsByUsername    │
│  3. repository.ExistsByEmail        │
│  4. password.Encrypt                │
│  5. repository.Create              │
│  6. notification.SendWelcomeEmail  │
└─────────────────────────────────────┘
  │
  ▼
Data Layer: MySQL
  │
  ▼
Response to Client
```

### 用户登录流程

```
Client
  │
  ▼
API Layer: POST /api/login
  │
  ▼
┌─────────────────────────────────────┐
│ Service Layer: Login               │
│                                     │
│  1. validator.Validate              │
│  2. repository.FindByUsername      │
│  3. password.Verify                │
│  4. auth.GenerateToken              │
│  5. repository.UpdateLastLogin     │
└─────────────────────────────────────┘
  │
  ├──▶ Cache: Redis (Token Storage)
  │
  ▼
Response to Client { token, user }
```

## 依赖关系图

```
┌─────────────┐     ┌─────────────┐
│    API     │────▶│   Service   │
│   Layer    │     │   Layer     │
└─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    Data     │
                    │   Layer     │
                    └─────────────┘
                           ▲
                           │
┌─────────────┐     ┌─────────────┐
│    Util     │◀────│ Repository  │
│   Layer     │     │   Layer     │
└─────────────┘     └─────────────┘
```

## 快速修复指南

### 如何修复用户注册问题

1. **检查点 1**: 验证请求参数
   - 文件: `src/user/api/user_handler.go`
   - 函数: `handleCreateUser`
   - 检查点: `validator.Validate(req)`

2. **检查点 2**: 检查用户是否已存在
   - 文件: `src/user/service/user_service.go`
   - 函数: `CreateUser`
   - 检查点: `repository.ExistsByUsername`

3. **检查点 3**: 密码加密问题
   - 文件: `src/user/util/password.go`
   - 函数: `Encrypt`
   - 检查点: bcrypt 加密是否正常工作

4. **检查点 4**: 数据库写入问题
   - 文件: `src/user/repository/user_repo.go`
   - 函数: `Create`
   - 检查点: SQL 执行是否成功

### 如何添加新 API

1. 在 `src/{module}/api/` 下创建新的 handler 文件
2. 在 service 层添加对应的业务逻辑函数
3. 在 repository 层添加数据访问函数
4. 在路由配置中注册新端点
5. 编写单元测试和集成测试

---

*此代码地图由 Code Map Generator 自动生成*
*最后更新: {时间戳}*