# Phase 2: PermissionGuard 权限守卫系统 - 设计文档

**版本**: v1.0
**日期**: 2026-04-15
**状态**: 草案待评审
**基于**: v3-upgrade-proposal.md §2.4 P2-a

---

## 1. 背景与动机

### 1.1 现状分析

当前 TraeMultiAgentSkill 的多 Agent 协作系统（Phase 1 已完成）具备以下能力：
- ✅ **Coordinator + Worker + Scratchpad** 协作框架
- ✅ **ConsensusEngine** 共识投票机制
- ✅ **BatchScheduler** 并行/串行混合调度
- ✅ **ContextCompressor** 3级上下文压缩
- ✅ **CoreRules** 20条核心规则（行为约束，非运行时拦截）

**关键差距**: 系统缺乏 **运行时操作权限控制**。Worker 执行任务时可能进行文件读写、Shell命令执行、网络请求等危险操作，但没有任何安全检查机制。

### 1.2 目标

构建 **PermissionGuard 权限守卫系统**，为多 Agent 协作提供 4 级权限分级和运行时操作拦截能力：

```
用户请求 → IntentRecognition → RoleMatch → SkillDispatch
                                                    ↓
                                            ┌─────────────────┐
                                            │  PermissionGuard │ ← 操作前检查
                                            │  (权限守卫)       │
                                            │                  │
                                            │  - 动作分类       │
                                            │  - 规则匹配       │
                                            │  - 级别判定       │
                                            │  - 审批流程       │
                                            └────────┬──────────┘
                                                     ↓
                                              允许 / 拦截 / 提示确认
```

### 1.3 设计原则

| 原则 | 说明 |
|------|------|
| **默认安全** | 未明确允许的操作默认需要确认 |
| **最小权限** | 每个 Worker 只拥有完成其角色所需的最小权限 |
| **可审计** | 所有权限决策记录在案，支持回溯 |
| **可配置** | 规则集可通过配置文件自定义 |
| **非阻塞式** | 不影响正常工作流，异步日志+同步决策 |

---

## 2. 核心架构设计

### 2.1 4级权限分级模型

```python
class PermissionLevel(Enum):
    DEFAULT = "default"     # 默认级别: 危险操作逐个提示用户确认
    PLAN     = "plan"       # 计划模式: 只读，禁止所有写操作
    AUTO     = "auto"       # 自动模式: AI分类器自动判断 + 白名单
    BYPASS   = "bypass"     # 绕过模式: 完全跳过检查（仅限最高信任度场景）
```

**各级别语义**:

| 级别 | 读文件 | 创建文件 | 修改文件 | 删除文件 | Shell命令 | 网络请求 | Git操作 |
|------|--------|---------|---------|---------|-----------|---------|---------|
| **PLAN** | ✅ 允许(只读) | ❌ 拒绝 | ❌ 拒绝 | ❌ 拒绝 | ❌ 拒绝 | ❌ 拒绝 | ⚠️ 只读git命令 |
| **DEFAULT** | ✅ 允许 | ⚠️ 确认路径+内容 | ⚠️ 确认变更范围 | 🔴 必须人工确认 | 🔴 必须人工确认 | 🤖 AI判断 | ⚠️ commit/push需确认 |
| **AUTO** | ✅ 允许 | 🤖 AI分类 | 🤖 AI分类 | ⚠️ 高风险需确认 | 🤖 AI分类 | 🤖 AI分类 | ✅ 允许常见操作 |
| **BYPASS** | ✅ 全部允许 | ✅ 全部允许 | ✅ 全部允许 | ✅ 全部允许 | ✅ 全部允许 | ✅ 全部允许 | ✅ 全部允许 |

### 2.2 动作类型分类 (ActionType)

```python
class ActionType(Enum):
    FILE_READ      = "file_read"        # 读取文件
    FILE_CREATE    = "file_create"      # 创建新文件
    FILE_MODIFY    = "file_modify"      # 修改已有文件
    FILE_DELETE    = "file_delete"      # 删除文件
    SHELL_EXECUTE  = "shell_execute"    # 执行Shell命令
    NETWORK_REQUEST = "network_request" # 网络请求
    GIT_OPERATION  = "git_operation"    # Git操作（commit/push/merge）
    ENVIRONMENT    = "environment"      # 环境变量修改
    PROCESS_SPAWN  = "process_spawn"    # 启动子进程
```

### 2.3 核心组件

#### 2.3.1 ProposedAction — 待审批的操作提案

```python
@dataclass
class ProposedAction:
    action_type: ActionType           # 操作类型
    target: str                       # 操作目标（文件路径/命令/URL等）
    description: str                  # 操作描述
    source_worker_id: Optional[str]   # 发起操作的Worker ID
    source_role_id: Optional[str]     # 发起操作的角色ID
    risk_score: float = 0.0           # 风险评分 [0.0-1.0]
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外上下文
    timestamp: datetime = field(default_factory=datetime.now)
```

#### 2.3.2 PermissionRule — 权限规则

```python
@dataclass
class PermissionRule:
    rule_id: str                      # 规则ID
    action_type: ActionType           # 适用动作类型
    pattern: str                      # 匹配模式（glob/regex/前缀匹配）
    required_level: PermissionLevel   # 所需最低权限级别
    description: str                  # 规则说明
    risk_boost: float = 0.0           # 风险加分
    tags: List[str] = field(default_factory=list)  # 标签
    enabled: bool = True              # 是否启用
```

#### 2.3.3 PermissionDecision — 权限决策结果

```python
class DecisionOutcome(Enum):
    ALLOWED    = "allowed"            # 允许执行
    DENIED     = "denied"             # 明确拒绝
    PROMPT     = "prompt"             # 需要用户确认
    ESCALATED  = "escalated"          # 升级处理（超出当前级别能力）

@dataclass
class PermissionDecision:
    action: ProposedAction            # 原始操作
    outcome: DecisionOutcome          # 决策结果
    matched_rule: Optional[PermissionRule]  # 命中的规则
    reason: str                       # 决策原因
    requires_confirmation: bool       # 是否需要用户交互
    confidence: float = 1.0           # 决策置信度
    decided_at: datetime = field(default_factory=datetime.now)
    decision_id: str = field(default_factory=lambda: f"pd-{uuid.uuid4().hex[:12]}")
```

#### 2.3.4 PermissionGuard — 权限守卫核心

```python
class PermissionGuard:
    """4级权限守卫系统"""

    def __init__(self,
                 current_level: PermissionLevel = PermissionLevel.DEFAULT,
                 rules: Optional[List[PermissionRule]] = None,
                 whitelist: Optional[Set[str]] = None,
                 audit_log: bool = True):

    def check(self, action: ProposedAction) -> PermissionDecision:
        """核心方法: 检查操作是否允许"""

    def auto_classify(self, action: ProposedAction) -> float:
        """AI自动分类: 返回风险评分 [0.0-1.0]"""

    def prompt_user(self, action: ProposedAction, reason: str) -> bool:
        """提示用户确认危险操作"""

    def add_rule(self, rule: PermissionRule) -> None:
        """动态添加规则"""

    def remove_rule(self, rule_id: str) -> None:
        """移除规则"""

    def set_level(self, level: PermissionLevel) -> None:
        """切换权限级别"""

    def get_audit_log(self, since: datetime = None, limit=100) -> List[Dict]:
        """获取审计日志"""

    def export_rules(self) -> List[Dict]:
        """导出所有规则"""

    def import_rules(self, rules_data: List[Dict]) -> int:
        """导入规则"""
```

### 2.4 规则匹配引擎

```
ProposedAction 进入
       ↓
  ┌──────────────────┐
  │  1. 类型过滤       │ → 快速定位 applicable_rules[action_type]
  └────────┬─────────┘
           ↓
  ┌──────────────────┐
  │  2. 模式匹配       │ → glob/regex/前缀 匹配 target
  └────────┬─────────┘
           ↓
  ┌──────────────────┐
  │  3. 级别比较       │ → current_level >= rule.required_level ?
  └────────┬─────────┘
           ↓
  ┌──────────────────┐
  │  4. 风险评估       │ → 基础分 + rule.risk_boost + auto_classify()
  └────────┬─────────┘
           ↓
  ┌──────────────────┐
  │  5. 决策生成       │ → ALLOWED / DENIED / PROMPT / ESCALATED
  └──────────────────┘
```

### 2.5 默认规则集

基于 Claude Code 的安全实践和项目实际需求：

```python
DEFAULT_RULES = [
    # ===== 文件读取 (低风险) =====
    PermissionRule("R001", ActionType.FILE_READ, "**/*",
                   PermissionLevel.PLAN, "读取任何文件", risk_boost=0.0),

    # ===== 文件创建 (中风险) =====
    PermissionRule("R002", ActionType.FILE_CREATE, "*.py",
                   PermissionLevel.AUTO, "创建Python文件", risk_boost=0.1),
    PermissionRule("R003", ActionType.FILE_CREATE, "*.md",
                   PermissionLevel.AUTO, "创建文档文件", risk_boost=0.05),
    PermissionRule("R004", ActionType.FILE_CREATE, "*.json",
                   PermissionLevel.DEFAULT, "创建JSON数据文件", risk_boost=0.15),
    PermissionRule("R005", ActionType.FILE_CREATE, "*",
                   PermissionLevel.DEFAULT, "创建其他类型文件", risk_boost=0.2),

    # ===== 文件修改 (中风险) =====
    PermissionRule("R006", ActionType.FILE_MODIFY, "*.py",
                   PermissionLevel.AUTO, "修改Python源码", risk_boost=0.2),
    PermissionRule("R007", ActionType.FILE_MODIFY, "*.md",
                   PermissionLevel.AUTO, "修改文档", risk_boost=0.1),
    PermissionRule("R008", ActionType.FILE_MODIFY, "*.json",
                   PermissionLevel.DEFAULT, "修改配置文件", risk_boost=0.25),
    PermissionRule("R009", ActionType.FILE_MODIFY, ".env*",
                   PermissionLevel.BYPASS, "修改环境变量文件", risk_boost=0.8),
    PermissionRule("R010", ActionType.FILE_MODIFY, "*/credentials*",
                   PermissionLevel.BYPASS, "修改凭据文件", risk_boost=0.95),
    PermissionRule("R011", ActionType.FILE_MODIFY, "*",
                   PermissionLevel.DEFAULT, "修改其他文件", risk_boost=0.25),

    # ===== 文件删除 (高风险) =====
    PermissionRule("R012", ActionType.FILE_DELETE, "__pycache__/**",
                   PermissionLevel.AUTO, "删除Python缓存", risk_boost=0.1),
    PermissionRule("R013", ActionType.FILE_DELETE, "*.pyc",
                   PermissionLevel.AUTO, "删除编译缓存", risk_boost=0.1),
    PermissionRule("R014", ActionType.FILE_DELETE, ".git/**",
                   PermissionLevel.BYPASS, "删除Git目录内容", risk_boost=0.99),
    PermissionRule("R015", ActionType.FILE_DELETE, "*",
                   PermissionLevel.BYPASS, "删除任意文件", risk_boost=0.9),

    # ===== Shell命令 (极高风险) =====
    PermissionRule("R016", ActionType.SHELL_EXECUTE, "cat *",
                   PermissionLevel.AUTO, "查看文件内容", risk_boost=0.05),
    PermissionRule("R017", ActionType.SHELL_EXECUTE, "ls *",
                   PermissionLevel.AUTO, "列出目录", risk_boost=0.05),
    PermissionRule("R018", ActionType.SHELL_EXECUTE, "git *",
                   PermissionLevel.AUTO, "Git只读命令", risk_boost=0.1),
    PermissionRule("R019", ActionType.SHELL_EXECUTE, "pip install *",
                   PermissionLevel.DEFAULT, "安装Python包", risk_boost=0.5),
    PermissionRule("R020", ActionType.SHELL_EXECUTE, "rm *",
                   PermissionLevel.BYPASS, "删除命令", risk_boost=0.95),
    PermissionRule("R021", ActionType.SHELL_EXECUTE, "sudo *",
                   PermissionLevel.BYPASS, "提权命令", risk_boost=1.0),
    PermissionRule("R022", ActionType.SHELL_EXECUTE, "*",
                   PermissionLevel.DEFAULT, "其他Shell命令", risk_boost=0.6),

    # ===== 网络请求 (中高风险) =====
    PermissionRule("R023", ActionType.NETWORK_REQUEST, "https://pypi.org/**",
                   PermissionLevel.AUTO, "PyPI包下载", risk_boost=0.15),
    PermissionRule("R024", ActionType.NETWORK_REQUEST, "https://github.com/**",
                   PermissionLevel.DEFAULT, "GitHub API访问", risk_boost=0.3),
    PermissionRule("R025", ActionType.NETWORK_REQUEST, "*",
                   PermissionLevel.DEFAULT, "其他网络请求", risk_boost=0.5),

    # ===== Git操作 =====
    PermissionRule("R026", ActionType.GIT_OPERATION, "status/diff/log/branch",
                   PermissionLevel.AUTO, "Git只读操作", risk_boost=0.05),
    PermissionRule("R027", ActionType.GIT_OPERATION, "commit/add",
                   PermissionLevel.DEFAULT, "Git提交操作", risk_boost=0.3),
    PermissionRule("R028", ActionType.GIT_OPERATION, "push",
                   PermissionLevel.DEFAULT, "Git推送操作", risk_boost=0.4),
    PermissionRule("R029", ActionType.GIT_OPERATION, "reset/rebase/force",
                   PermissionLevel.BYPASS, "Git危险操作", risk_boost=0.9),

    # ===== 环境变量 =====
    PermissionRule("R030", ActionType.ENVIRONMENT, "*",
                   PermissionLevel.BYPASS, "修改环境变量", risk_boost=0.7),
]
```

---

## 3. 与协作系统集成设计

### 3.1 Worker 执行流程集成点

```
Worker.execute(task)
    ↓
    ① 解析任务 → 生成操作列表
    ↓
    ② 对每个操作调用 permission_guard.check(action)
    ↓
    ├── ALLOWED  → 执行操作
    ├── DENIED   → 记录拒绝日志，跳过操作
    ├── PROMPT   → 暂停，等待用户确认后继续
    └── ESCALATED → 写入 Scratchpad 冲突，触发共识流程
    ↓
    ③ 收集结果 → 返回 WorkerResult
```

### 3.2 Coordinator 层面集成

```python
class Coordinator:
    def __init__(self, ..., permission_guard=None):
        self.permission_guard = permission_guard or PermissionGuard()

    def execute_plan(self, plan):
        for batch in plan.batches:
            for task in batch.tasks:
                worker = self._get_worker_for_task(task)
                result = worker.execute_with_guard(task, self.permission_guard)
                # ...
```

### 3.3 与 Consensus 的联动

当操作被 ESCALATED 时：
1. PermissionGuard 在 Scratchpad 中写入一条 `CONFLICT` 类型条目
2. Coordinator 的 `resolve_conflicts()` 检测到该冲突
3. 发起共识投票：是否允许该操作？
4. 多个 Worker 投票决定
5. 共识通过 → 临时放行；未通过 → 保持拒绝

---

## 4. AI 自动分类器 (AUTO 模式)

### 4.1 分类策略

AUTO 模式的核心是 `auto_classify()` 方法，对无法用规则精确匹配的操作进行智能风险评估：

**评估维度**:

| 维度 | 权重 | 评估方式 |
|------|------|---------|
| **目标敏感度** | 30% | 文件名/路径是否包含敏感词(credentials/.env/secret/key) |
| **操作破坏性** | 25% | 是否涉及删除/覆盖/强制操作 |
| **目标范围** | 20% | 通配符范围(* vs 具体) |
| **来源可信度** | 15% | Worker角色+历史表现 |
| **上下文合理性** | 10% | 操作是否符合当前任务上下文 |

### 4.2 白名单机制

AUTO 模式维护一个白名单集合，已确认安全的操作直接放行：
- 常见开发工具链操作（npm install、pip list、python -m pytest）
- 项目内部文件的常规修改
- Git 只读操作

### 4.3 学习反馈循环

```
用户确认操作 → 记录到审计日志 → 分析模式 → 更新白名单/规则
                                          ↑
用户拒绝操作 ──────────────────────────────┘
```

---

## 5. 审计日志系统

### 5.1 日志结构

```python
@dataclass
class AuditEntry:
    entry_id: str
    action: ProposedAction
    decision: PermissionDecision
    duration_ms: int                    # 决策耗时
    guard_level: PermissionLevel        # 当时的权限级别
    user_response: Optional[str]        # 用户响应（如有）
    session_id: str                     # 会话ID
    timestamp: datetime
```

### 5.2 日志查询接口

```python
def get_audit_log(self,
                  since: datetime = None,
                  until: datetime = None,
                  action_type: ActionType = None,
                  outcome: DecisionOutcome = None,
                  worker_id: str = None,
                  risk_min: float = None,
                  limit: int = 100) -> List[AuditEntry]:
```

### 5.3 统计报告

```python
def get_security_report(self) -> Dict:
    return {
        "total_checks": N,
        "allowed": N,
        "denied": N,
        "prompted": N,
        "escalated": N,
        "avg_risk_score": X.XX,
        "top_denied_actions": [...],
        "risk_trend": [...],
    }
```

---

## 6. 文件结构

```
scripts/collaboration/
├── permission_guard.py          ← 核心: PermissionGuard + 数据模型
├── permission_guard_test.py     ← 测试套件
├── __init__.py                  ← 更新导出
├── coordinator.py               ← 更新: 集成权限检查
└── ...

docs/
├── architecture/
│   └── v3-phase2-permission-design.md  ← 本文档
├── product-manager/
│   └── USER_STORIES_P2.md              ← PM: 用户故事
└── test-expert/
    ├── TEST_PLAN_P2.md                 ← Tester: 测试计划
    ├── TEST_CASES_P2.md                ← Tester: 测试用例
    └── TEST_REPORT_P2.md               ← Tester: 测试报告
```

---

## 7. 验收标准

| 编号 | 标准 | 验证方式 |
|------|------|---------|
| AC-01 | 4级权限级别正确实现，级别间行为差异明显 | 单元测试 |
| AC-02 | 30条默认规则覆盖常见操作场景 | 规则覆盖率测试 |
| AC-03 | 危险操作（rm -rf / sudo）被正确拦截 | 安全边界测试 |
| AC-04 | PLAN模式完全禁止写操作 | 模式隔离测试 |
| AC-05 | AUTO模式的AI分类器返回合理风险评分 | 分类准确率测试 |
| AC-06 | 审计日志完整记录每次决策 | 日志完整性测试 |
| AC-07 | 与Coordinator/Worker无缝集成 | 集成E2E测试 |
| AC-08 | 规则可动态添加/删除/导入/导出 | 规则管理测试 |
| ESCALATED操作能触发共识流程 | 联动测试 |
| 性能: 单次check() < 5ms | 性能基准测试 |

---

## 8. 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| 规则过于严格导致正常工作受阻 | 中 | 中 | 提供宽松的AUTO模式和快速白名单添加 |
| AI分类器误判 | 中 | 低 | 保留人工确认通道，分类结果仅作参考 |
| 审计日志膨胀 | 低 | 低 | 自动轮转 + 按时间分区 |
| 性能开销影响协作效率 | 低 | 中 | 缓存规则匹配结果，热点路径优化 |
| BYPASS模式被滥用 | 极低 | 极高 | 仅在代码中硬编码启用条件，不暴露给普通用户 |

---

## 9. 成功指标

| 指标 | 基线 | 目标 | 测量方式 |
|------|------|------|---------|
| 危险操作拦截率 | 0% | **100%** | 审计日志统计 |
| 误拦率（正常操作被拦截） | N/A | **< 5%** | 用户反馈统计 |
| 平均决策延迟 | N/A | **< 5ms** | 性能基准 |
| 规则覆盖率（操作类型） | N/A | **> 90%** | 规则矩阵分析 |
| 安全事件可追溯性 | 无 | **100%** | 审计日志完整性 |
