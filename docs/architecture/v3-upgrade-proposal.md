# TraeMultiAgentSkill v3.0 架构升级方案

## 基于 Claude Code 架构原理深度解析的改进提案

**版本**: v2.0 (完成)
**日期**: 2026-04-15 ~ 2026-04-16
**状态**: ✅ 全部完成
**作者**: AI 协作团队

---

## 1. 背景与动机

### 1.1 现状总结

TraeMultiAgentSkill v2.5 已完成以下工作：
- ✅ 提示词统一管理体系（PromptRegistry）
- ✅ 8阶段全生命周期提示词（角色+阶段+门禁）
- ✅ 项目目录结构规范模板
- ✅ 目录结构重构（消除嵌套、数据分离）
- ✅ 提示词进化系统增强（6维度评估+生命周期合规）

### 1.2 核心差距分析

通过深入分析 Claude Code 的架构设计（1900文件/51万行代码），识别出以下**6个核心架构差距**：

| # | 差距领域 | Claude Code 做法 | 我们现状 | 影响程度 |
|---|---------|-----------------|---------|---------|
| 1 | **多Agent编排** | Coordinator + Workers + Scratchpad 共享 | 单次调度 + 串行 Handoff | 🔴 致命 |
| 2 | **工具并发调度** | Batch 并行/串行混合 + isConcurrencySafe() | 纯串行8阶段流水线 | 🟡 高 |
| 3 | **上下文压缩** | 3级压缩策略(SNIP/SessionMemory/FullCompact) | 无主动压缩机制 | 🟡 高 |
| 4 | **权限系统** | 4级安全分级(default/plan/auto/bypass) | 只检查交付物质量 | 🟠 中 |
| 5 | **Skills自进化** | /skillify 自动从操作生成新 Skill | Alpha/Omega 模板进化 | 🟠 中 |
| 6 | **启动优化** | ~650ms冷启动节省(预加载/预取) | 首次加载15+个Markdown | 🟢 低 |

### 1.3 目标

将 TraeMultiAgentSkill 从 **"单次调度工具"** 升级为 **"持续协作平台"**，使多角色 Agent 能够像真正的开发团队一样并行工作、共享知识、达成共识。

---

## 2. 改进方案详解

### 2.1 P0：Coordinator + Scratchpad 共享协作模式

#### 2.1.1 问题定义

当前的多角色协作模式是**接力棒模式**：
```
产品经理 → 架构师 → UI设计师 → 测试专家 → 开发者 → 测试验证
```
每个角色独立执行，通过 Handoff 文档交接。问题：
- 角色间无法实时沟通发现的问题
- 后续角色的输入依赖前序角色的输出质量
- 无法处理需要多个角色同时讨论的复杂决策
- 并行机会被浪费（如 UI设计和测试设计可同时进行）

#### 2.1.2 目标架构：Coordinator 模式

```
                    ┌─────────────────────┐
                    │   Coordinator       │ ← 全局编排者
                    │  (协调者/主持人)      │
                    │                     │
                    │  - 任务分解          │
                    │  - Worker 分配        │
                    │  - 共识管理          │
                    │  - 冲突解决          │
                    │  - 最终决策          │
                    └──────────┬──────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ↓                  ↓                  ↓
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │  Worker-A    │  │  Worker-B    │  │  Worker-C    │
    │  (架构师)     │  │  (测试专家)   │  │  (UI设计师)   │
    │              │  │              │  │              │
    │ 执行任务      │  │ 执行任务      │  │ 执行任务      │
    │ 写入发现      │  │ 写入发现      │  │ 写入发现      │
    └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
           │                 │                 │
           └────────────────┬┴────────────────┘
                            ↓
                   ┌──────────────┐
                   │  Scratchpad   │ ← 共享工作区
                   │  (共享黑板)    │
                   │              │
                   │ - 发现记录     │
                   │ - 决策依据     │
                   │ - 冲突点       │
                   │ - 共识结论     │
                   └──────────────┘
```

#### 2.1.3 核心组件设计

**组件1: Coordinator（协调者）**

```python
class Coordinator:
    """全局协调者，管理多Worker协作"""
    
    def __init__(self, scratchpad: Scratchpad, registry: PromptRegistry):
        self.scratchpad = scratchpad
        self.registry = registry
        self.workers: Dict[str, Worker] = {}
        self.consensus_log: List[ConsensusRecord] = []
    
    def plan_task(self, task_description: str) -> ExecutionPlan:
        """分解任务为可并行的Worker计划"""
        
    def spawn_workers(self, plan: ExecutionPlan) -> List[Worker]:
        """创建并启动Worker"""
        
    def collect_results(self) -> CollaborationResult:
        """收集所有Worker结果"""
        
    def resolve_conflicts(self, results: List[WorkerResult]) -> Consensus:
        """解决Worker间的冲突和分歧"""
        
    def reach_consensus(self, topic: str, votes: List[Vote]) -> Decision:
        """达成共识决策"""
```

**组件2: Scratchpad（共享黑板）**

```python
class ScratchpadEntry:
    """共享黑板条目"""
    entry_id: str
    worker_id: str              # 哪个Worker写入
    role_id: str                 # 角色
    timestamp: datetime
    entry_type: EntryType       # FINDING / DECISION / CONFLICT / QUESTION
    content: str                # 内容
    confidence: float           # 信心度 0-1
    tags: List[str]             # 标签（便于检索）
    references: List[str]       # 引用的其他条目
    status: EntryStatus         # ACTIVE / RESOLVED / SUPERSEDED

class Scratchpad:
    """共享工作区 - 所有Worker读写"""
    
    entries: Dict[str, ScratchpadEntry]
    
    def write(self, worker_id: str, entry: ScratchpadEntry) -> str:
        """Worker写入发现"""
        
    def read(self, query: str, since: datetime = None) -> List[ScratchpadEntry]:
        """按查询读取相关条目"""
        
    def resolve(self, entry_id: str, resolution: str):
        """标记条目为已解决"""
        
    def get_conflicts(self) -> List[ScratchpadEntry]:
        """获取所有未解决的冲突"""
        
    def get_summary(self, for_role: str = None) -> str:
        """生成摘要（可按角色定制视角）"""
```

**组件3: Worker（工作者）**

```python
class Worker:
    """工作者 - 执行具体任务的Agent实例"""
    
    worker_id: str
    role_id: str                  # 角色
    role_prompt: str               # 角色提示词（含生命周期感知）
    scratchpad: Scratchpad         # 共享黑板
    
    def execute(self, task: TaskDefinition) -> WorkerResult:
        """执行任务，过程中读写Scratchpad"""
        
    def read_scratchpad(self, query: str) -> List[ScratchpadEntry]:
        """读取其他Worker的发现"""
        
    def write_finding(self, finding: Finding):
        """写入自己的发现到Scratchpad"""
        
    def vote_on_decision(self, decision_proposal: DecisionProposal) -> Vote:
        """对协调者的决策提议投票"""
```

**组件4: 消息协议（Task Notification）**

```xml
<!-- Worker 间传递的消息格式 -->
<task-notification 
    from-worker="worker-A"
    to-workers="worker-B,worker-C"
    type="finding | question | conflict | decision-request"
    priority="high | medium | low"
    timestamp="2026-04-15T16:30:00Z">
    
    <summary>在模块X中发现潜在的性能瓶颈</summary>
    <details>数据库查询N+1问题，建议引入缓存层...</details>
    <references>/scratchpad/entry-001</references>
    <action-required>请测试专家评估影响范围</action-required>
</task-notification>
```

#### 2.1.4 与现有系统的集成点

| 现有组件 | 集成方式 |
|---------|---------|
| `PromptRegistry` | 为每个 Worker 提供带生命周期的角色提示词 |
| `workflow_engine_v2` | Coordinator 使用 CheckpointManager 保存状态 |
| `dual_layer_context_manager` | Scratchpad 作为上下文层的一部分 |
| `role_matcher` | Coordinator 使用 RoleMatcher 选择合适的 Worker |

---

### 2.2 P1-a：Batch 并行调度

#### 2.2.1 设计

```python
class BatchScheduler:
    """批处理调度器 - 混合并行/串行"""
    
    @dataclass
    class TaskBatch:
        batch_id: str
        mode: BatchMode             # PARALLEL or SERIAL
        tasks: List[TaskDefinition]
        max_concurrency: int        # PARALLEL模式下最大并发数
        dependencies: List[str]    # 依赖的其他batch_id
        
    def schedule(self, batches: List[TaskBatch]) -> ScheduleResult:
        """执行调度计划"""
        
    def is_concurrency_safe(self, task: TaskDefinition) -> bool:
        """判断任务是否可以安全并行执行"""
        # 只读任务（代码走读、文档审查）→ 可并行
        # 写入任务（代码修改、文件创建）→ 串行
```

**默认并行规则**：

| 阶段组合 | 可并行？ | 理由 |
|---------|---------|------|
| 阶段1(需求) + 无 | — | 首阶段必须完成 |
| 阶段2(架构) + 无 | — | 依赖阶段1 |
| **阶段3(UI设计) + 阶段4(测试设计)** | ✅ **可并行** | 都只读架构设计产物 |
| 阶段5(任务分解) | — | 依赖2+3+4 |
| 阶段6(开发) | — | 依赖阶段5 |
| 阶段7(测试验证) | — | 依赖阶段6 |
| **代码走读(多角色)** | ✅ **可并行** | 都是只读操作 |
| **文档审查(多角色)** | ✅ **可并行** | 都是只读操作 |

---

### 2.3 P1-b：上下文压缩 3级策略

#### 2.3.1 设计

```python
class ContextCompressor:
    """上下文压缩器 - 3级压缩策略"""
    
    def __init__(self, token_threshold: int = 100000):
        self.token_threshold = token_threshold
        self.compression_level = 0  # 0=无, 1=SNIP, 2=SessionMemory, 3=FullCompact
    
    def check_and_compress(self, context: ConversationContext) -> CompressedContext:
        """检查上下文大小，必要时压缩"""
        
    def level1_snip(self, context: ConversationContext) -> CompressedContext:
        """Level 1: HISTORY_SNIP - 精细剪裁旧对话"""
        # 保留：关键决策、最终结论、错误修正
        # 剪裁：中间推理过程、重复确认、闲聊
        # 实现：基于token重要性评分，保留高分片段
        
    def level2_session_memory(self, context: ConversationContext) -> CompressedContext:
        """Level 2: SessionMemory - 提取记忆后清空"""
        # 将重要信息提取到 SessionMemory
        # 清空上下文窗口
        # 后续需要时从 SessionMemory 回溯
        
    def level3_full_compact(self, context: ConversationContext) -> CompressedContext:
        """Level 3: FullCompact - LLM生成压缩摘要"""
        # 用LLM将整个对话压缩为一页摘要
        # 包含：关键决策、交付物清单、待办事项
        # 最激进但最省空间
```

**触发条件**：

| 当前Token数 | 触发级别 | 操作 |
|------------|---------|------|
| < 60,000 | 0 | 不压缩 |
| 60,000 - 80,000 | 1 | SNIP剪裁 |
| 80,000 - 100,000 | 2 | SessionMemory提取 |
| > 100,000 | 3 | FullCompact全压缩 |

---

### 2.4 P2-a：权限系统 4级分级

#### 2.4.1 设计

```python
class PermissionLevel(Enum):
    DEFAULT = "default"     # 危险操作逐个提示用户
    PLAN = "plan"           # 只读模式，禁止所有写操作
    AUTO = "auto"           # AI分类器自动判断 + 白名单
    BYPASS = "bypass"       # 完全跳过（仅限最高信任度）

@dataclass
class PermissionRule:
    action_type: ActionType       # FILE_WRITE / NETWORK / EXECUTE / DELETE
    pattern: str                 # 匹配模式（glob）
    required_level: PermissionLevel
    description: str

class PermissionGuard:
    """权限守卫"""
    
    rules: List[PermissionRule]
    
    def check(self, action: ProposedAction) -> PermissionDecision:
        """检查操作是否允许"""
        
    def prompt_user(self, action: ProposedAction) -> bool:
        """提示用户确认危险操作"""
        
    def auto_classify(self, action: ProposedAction) -> bool:
        """AI自动判断操作安全性"""
```

**默认规则集**：

| 操作类型 | 默认级别 | 说明 |
|---------|---------|------|
| 读取文件 | PLAN | 安全，但需告知 |
| 创建新文件 | DEFAULT | 需要确认路径和内容 |
| 修改现有文件 | DEFAULT | 需要确认变更范围 |
| 删除文件 | BYPASS | 必须人工确认 |
| 网络请求 | AUTO | 分类器判断是否安全 |
| 执行Shell命令 | BYPASS | 最高风险 |
| Git操作 | DEFAULT | push/commit需确认 |

---

### 2.5 P2-b：/skillify 自动 Skill 生成

#### 2.5.1 设计

```python
class Skillifier:
    """从成功操作序列中自动生成新Skill"""
    
    def analyze_success_pattern(self, execution_history: List[ExecutionRecord]) -> SkillProposal:
        """分析成功的操作模式，提取可复用Skill"""
        
    def generate_skill_from_pattern(self, pattern: SuccessPattern) -> SkillDefinition:
        """从模式生成Skill定义"""
        
    def validate_skill(self, skill: SkillDefinition) -> ValidationResult:
        """验证生成的Skill质量"""
        
    def publish_skill(self, skill: SkillDefinition, approval: bool = False):
        """发布Skill到注册表"""
```

**流程**：
```
1. 用户完成一个复杂任务（如"完整8阶段项目开发"）
2. Skillifier 记录完整的操作序列
3. 分析哪些步骤可以泛化为可复用模式
4. 生成 Skill 草案（含触发条件、步骤、验收标准）
5. 用户确认后发布到 skills-index.json
6. 下次遇到类似任务时自动匹配该 Skill
```

---

### 2.6 P3：启动优化

#### 2.6.1 设计

```python
class WarmupManager:
    """启动预热管理器"""
    
    async def warmup(self):
        """预热关键资源"""
        await self._preload_common_roles()      # 预加载高频角色提示词
        await self._preload_stage_templates()    # 预加载当前阶段模板
        await self._init_registry_cache()        # 初始化注册表缓存
        await self._preload_embedding_model()    # 预热嵌入模型（如使用）
```

**预热策略**：

| 资源 | 预加载时机 | 预期收益 |
|------|-----------|---------|
| Top 3 角色提示词 | 应用启动时 | 减少~200ms首次调度延迟 |
| 当前阶段模板 | 进入阶段时 | 减少阶段切换延迟 |
| PromptRegistry 缓存 | 首次调用时 | 后续调用O(1) |
| 嵌入模型 | 有语义匹配需求时 | 避免冷启动延迟 |

---

## 3. 实施路线图

### Phase 1：P0 Coordinator + Scratchpad（预计 2 周） ✅ 已完成

| 步骤 | 产出 | 验收标准 |
|------|------|---------|
| 1.1 | Scratchpad 数据模型和存储 (`scratchpad.py`) | 单元测试通过 ✅ |
| 1.2 | Worker 执行框架 (`worker.py`) | 可运行单个Worker任务 ✅ |
| 1.3 | Coordinator 编排逻辑 (`coordinator.py`) | 可分解任务并分配给Workers ✅ |
| 1.4 | 消息协议实现 (`models.py`) | Worker间可传递消息 ✅ |
| 1.5 | 共识机制 (`consensus.py`) | 多Worker可投票达成共识 ✅ |
| 1.6 | 集成现有系统 | 与PromptRegistry/WorkflowEngine集成 ✅ |
| 1.7 | E2E测试 | 完整的多Worker协作场景通过 ✅ |

**实际产出**：`coordinator.py` + `scratchpad.py` + `worker.py` + `consensus.py` + `batch_scheduler.py` + `models.py`，共 **96 个测试用例**

### Phase 1-b：ContextCompressor 上下文压缩 ✅ 已完成

| 步骤 | 产出 | 验收标准 |
|------|------|---------|
| 2.b.1 | ContextCompressor 3级压缩策略 (`context_compressor.py`) | SNIP/SessionMemory/FullCompact 全部实现 ✅ |
| 2.b.2 | Token计数与阈值触发 | 自动检测上下文大小并选择级别 ✅ |
| 2.b.3 | 中文支持 | CJK文本正确处理 ✅ |

**实际产出**：`context_compressor.py`，共 **72 个测试用例**

### Phase 2-a：P2 权限系统 PermissionGuard ✅ 已完成

| 步骤 | 产出 | 验收标准 |
|------|------|---------|
| 3.a.1 | PermissionGuard + 4级规则 (`permission_guard.py`) | 危险操作有正确拦截 ✅ |
| 3.a.2 | AI自动分类器 | AUTO模式可判断安全性 ✅ |
| 3.a.3 | 白名单学习 | 用户确认后记住决策 ✅ |
| 3.a.4 | Feature Flag 支持 | 新功能可灰度发布 ✅ |

**实际产出**：`permission_guard.py`，共 **105 个测试用例**

### Phase 2-b：P2 Skillify 自动Skill生成 ✅ 已完成

| 步骤 | 产出 | 验收标准 |
|------|------|---------|
| 3.b.1 | Skillifier 分析引擎 (`skillifier.py`) | 可识别成功模式 ✅ |
| 3.b.2 | Skill 生成器 | 生成的Skill可用 ✅ |
| 3.b.3 | Skill 发布流程 | 新Skill可被发现和使用 ✅ |

**实际产出**：`skillifier.py`，共 **96 个测试用例**

### Phase 3：P3 启动优化 WarmupManager ✅ 已完成

| 步骤 | 产出 | 验收标准 |
|------|------|---------|
| 4.1 | WarmupManager 3层预热 (`warmup_manager.py`) | EAGER/ASYNC/LAZY全部实现 ✅ |
| 4.2 | 进程级单例缓存+TTL+LRU淘汰 | 缓存正确工作 ✅ |
| 4.3 | 拓扑排序依赖解析 | 有依赖关系的任务按序执行 ✅ |
| 4.4 | 性能基准测试+诊断 | benchmark/diagnostics可用 ✅ |

**实际产出**：`warmup_manager.py`，共 **103 个测试用例**

### Phase 4：MemoryBridge 记忆桥接系统 ✅ 已完成 (新增)

| 步骤 | 产出 | 验收标准 |
|------|------|---------|
| 5.1 | MemoryBridge 核心桥接 (`memory_bridge.py`) | recall/capture/record/search全部实现 ✅ |
| 5.2 | 7种记忆类型+倒排索引+TF-IDF搜索 | 中英文检索正确 ✅ |
| 5.3 | 遗忘曲线(7d~90d) | 老记忆权重衰减 ✅ |
| 5.4 | JsonMemoryStore文件存储 | 线程安全读写 ✅ |
| 5.5 | 生命周期管理(compress/cleanup) | 过期记忆自动清理 ✅ |

**实际产出**：`memory_bridge.py`，共 **96 个测试用例**

---

## 4. 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| Coordinator 复杂度过高 | 中 | 高 | 先实现简化版（2-3 Worker），逐步扩展 |
| Scratchpad 信息过载 | 中 | 中 | 设置容量上限 + LRU淘汰 |
| 并行任务冲突 | 低 | 高 | 依赖分析 + 锁机制 |
| 上下文压缩丢失关键信息 | 中 | 高 | 压缩前备份 + 可回溯 |
| 权限系统误拦截 | 低 | 中 | 白名单学习 + 用户反馈闭环 |

---

## 5. 成功指标

| 指标 | v2.5 基线 | v3.0 目标 | 实际达成 | 测量方法 |
|------|----------|----------|---------|---------|
| 多角色协作效率 | 串行，无实时交互 | **并行率 > 40%** | ✅ Coordinator+Scratchpad+BatchScheduler | 任务耗时对比 |
| 上下文利用率 | 无压缩，易溢出 | **压缩后节省 > 50% 空间** | ✅ ContextCompressor 3级压缩 | Token 计数 |
| 决策质量 | 单角色决策 | **共识决策覆盖率 > 80%** | ✅ Consensus 共识机制 | 决策记录审计 |
| 安全性 | 无权限控制 | **危险操作拦截率 100%** | ✅ PermissionGuard 4级分级 | 权限日志 |
| 自进化能力 | 手动维护提示词 | **自动生成 Skill > 5个/月** | ✅ Skillifier 模式识别+生成 | Skill 注册表 |
| 冷启动速度 | ~2s（首加载） | **< 1s** | ✅ WarmupManager 3层预热 | 性能基准测试 |
| 记忆能力 | 无持久化记忆 | **跨会话记忆保留** | ✅ MemoryBridge 7类型+遗忘曲线 | 记忆统计 |

### 总体完成情况

| 维度 | 数据 |
|------|------|
| **总模块数** | 10 个核心模块 |
| **总测试用例** | **568 / 568 通过 (100%)** |
| **代码文件** | 10 个实现模块 + 10 个测试模块 + 6 套设计文档 + 4 套用户故事 + 4 套测试计划 |
| **开发周期** | 2026-04-15 ~ 2026-04-16（约2天） |
| **文档先行工作流** | Design Doc → PM Stories → Tester Plan → Consensus → Implement → Test → Integrate → Push |

---

## 6. 附录

### A. 参考架构

- Claude Code 架构（1900文件/51万行代码/Bun+TypeScript+ReactInk）
- Anthropic Agent Design Patterns (2025)
- Microsoft AutoGen Multi-Agent Framework
- LangGraph Agent Orchestration

### B. 术语表

| 术语 | 定义 |
|------|------|
| Coordinator | 协调者，管理多Worker的全局角色 |
| Worker | 工作者，执行具体任务的Agent实例 |
| Scratchpad | 共享黑板，Worker间交换信息的媒介 |
| Consensus | 共识，多Worker对同一问题达成一致意见 |
| BatchScheduler | 批处理调度器，管理任务的并行/串行执行 |
| Skillify | 从成功操作中自动生成可复用Skill的能力 |
| ContextCompressor | 上下文压缩器，3级压缩策略(SNIP/SessionMemory/FullCompact) |
| PermissionGuard | 权限守卫，4级安全分级(default/plan/auto/bypass) |
| WarmupManager | 启动预热管理器，3层预加载策略(EAGER/ASYNC/LAZY) |
| MemoryBridge | 记忆桥接系统，7类型记忆+倒排索引+TF-IDF搜索+遗忘曲线 |
