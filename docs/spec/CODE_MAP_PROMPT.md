# 代码地图分析 Prompt 模板

## 用途

此 prompt 模板用于指导 agent 如何使用代码地图生成器生成项目的代码结构文档，以及如何阅读和理解代码地图。

## 场景 1：首次分析项目

### 用户请求
```
帮我理解这个项目的代码结构
```

### Agent 执行流程

1. **生成代码地图**
```
请生成项目代码地图：
```
python /Users/wangwei/claw/.trae/skills/trae-multi-agent/scripts/code_map_generator_v2.py <项目路径>
```

2. **阅读代码地图**
读取生成的 CODE_MAP.md 文件，分析以下内容：
- 项目概览：了解项目技术栈和代码规模
- 架构分层：理解系统的分层结构
- 模块详情：定位核心功能所在的模块

3. **总结项目结构**
```
根据代码地图分析，这个项目的结构如下：

**项目规模**: XX 个源文件，XX 行代码

**技术栈**:
- 语言: Python, JavaScript
- 框架: Django, React

**架构分层**:
1. API Layer (25 文件) - 处理 HTTP 请求
2. Service Layer (40 文件) - 业务逻辑
3. Data Layer (30 文件) - 数据持久化
...

**核心模块**:
- user 模块 - 用户管理
- order 模块 - 订单管理
...

**调用关系**:
客户端 → API Layer → Service Layer → Data Layer
```

## 场景 2：定位需要修复的代码

### 用户请求
```
修复用户登录失败的问题
```

### Agent 执行流程

1. **生成/更新代码地图**（如果已有可跳过）
```
python /Users/wangwei/claw/.trae/skills/trae-multi-agent/scripts/code_map_generator_v2.py <项目路径>
```

2. **搜索相关代码**
根据代码地图中的"快速修复指南"和模块结构，定位登录相关的代码：
- API Layer: `api/auth.py` 或 `routes/login.py`
- Service Layer: `service/auth_service.py`
- Data Layer: `repository/user_repo.py`

3. **分析调用链**
```
登录流程分析：

1. 客户端 POST /api/login
2. API Layer: handle_login() 接收请求
3. Service Layer: AuthService.login() 验证用户
   - 调用 UserRepository.find_by_username()
   - 调用 PasswordUtil.verify()
   - 调用 TokenUtil.generate()
4. 返回登录响应

可能的问题点：
- 用户名不存在
- 密码验证失败
- Token 生成失败
```

4. **执行修复**
根据分析定位问题并进行修复。

## 场景 3：理解模块依赖

### 用户请求
```
订单模块是如何依赖其他模块的？
```

### Agent 执行流程

1. **阅读代码地图中的模块详情**
```
根据代码地图：

**订单模块 (order)**

包含文件:
- api/order_api.go - 订单 API
- service/order_service.go - 订单业务
- repository/order_repo.go - 订单数据访问
- model/order.go - 订单模型

导出接口:
- CreateOrder() - 创建订单
- GetOrder() - 获取订单
- CancelOrder() - 取消订单

依赖模块:
- user 模块 (获取用户信息)
- product 模块 (验证商品)
- payment 模块 (处理支付)
- inventory 模块 (扣减库存)
```

2. **查看调用流程图**
```
调用链:

CreateOrder
├── UserService.GetUser()      # 获取用户信息
├── ProductService.GetProduct() # 获取商品信息
├── InventoryService.Reserve() # 预留库存
├── PaymentService.Charge()    # 处理支付
└── OrderRepository.Save()     # 保存订单
```

## 场景 4：添加新功能

### 用户请求
```
在用户模块添加一个新功能：用户头像上传
```

### Agent 执行流程

1. **定位模块位置**
```
根据代码地图，用户模块位于:
- 路径: src/user/
- API: src/user/api/user_api.go
- Service: src/user/service/user_service.go
- Repository: src/user/repository/user_repo.go
```

2. **确定修改范围**
```
需要修改的文件:
1. API Layer: src/user/api/user_api.go
   - 添加上传端点: POST /api/users/{id}/avatar

2. Service Layer: src/user/service/user_service.go
   - 添加业务逻辑: UploadAvatar()

3. 新增文件: src/user/util/file_util.go
   - 文件处理工具函数

4. 配置更新: config/storage.yaml
   - 文件存储配置
```

3. **执行实现**
按照代码地图指示的位置添加新功能。

## 代码地图关键部分解读

### 架构分层表

| 层级 | 职责 | 常见问题排查点 |
|------|------|---------------|
| API Layer | 接收 HTTP 请求 | 路由配置、参数验证 |
| Service Layer | 业务逻辑处理 | 业务规则、事务管理 |
| Data Layer | 数据持久化 | SQL 性能、连接池 |
| Middleware Layer | 请求拦截处理 | 认证、限流、日志 |
| Utility Layer | 通用工具函数 | 工具函数 bug |

### 文件详情

每个文件的详情包括：
- **路径**: 文件的相对路径
- **语言**: 编程语言
- **复杂度**: low/medium/high
- **导入依赖**: 该文件依赖的其他模块
- **类/函数**: 定义的类和函数列表
- **函数签名**: 参数、返回值、调用关系

### 快速修复指南

针对常见错误类型，提供的问题定位路径：

| 问题类型 | 排查层级 | 关键字 |
|----------|----------|--------|
| 404 错误 | API Layer | routes, controller |
| 权限不足 | Middleware | auth, permission |
| 业务逻辑错误 | Service Layer | service, validate |
| 数据库错误 | Data Layer | repository, query |
| 前端显示问题 | UI Layer | component, view |

## 代码地图作为项目规则

将代码地图作为项目规则使用时，可以让 agent：

1. **理解架构约束**: 按照分层架构组织代码
2. **遵循调用约定**: 按照代码地图中的调用链进行开发
3. **快速定位问题**: 按照快速修复指南排查问题
4. **保持一致性**: 新功能开发遵循现有模块结构

```
项目规则:
- 所有 API 端点必须在 API Layer
- 所有业务逻辑必须在 Service Layer
- 所有数据库访问必须在 Data Layer
- Service Layer 禁止直接调用 API Layer
- 模块间调用按照代码地图中的依赖关系进行
```