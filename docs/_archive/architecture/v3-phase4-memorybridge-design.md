# Phase 4: MemoryBridge 记忆桥接系统 - 设计文档

**版本**: v1.0
**日期**: 2026-04-16
**状态**: 设计完成
**依赖**: Phase 1~3 全部完成 (Coordinator + Compressor + Guard + Skillify + Warmup)

---

## 1. 背景与动机

### 1.1 现状：记忆孤岛

DevSquad 已拥有丰富的 `data/memory-bank/` 数据层，但与协作系统完全脱节：

| 子系统 | 路径 | 数据量 | 与协作系统集成？ |
|--------|------|--------|---------------|
| 知识库 (KnowledgeBase) | `memory-bank/knowledge_base/domains/` | 3域×N条 | ❌ 未集成 |
| 分析案例 (AnalysisCases) | `memory-bank/analysis_cases/` | 12条 | ❌ 未集成 |
| 提示词进化 (PromptEvolution) | `memory-bank/prompt_evolution/` | 7组 | ❌ 未集成 |
| 用户反馈 (UserFeedback) | `memory-bank/user_experience/feedback/` | 8条 | ❌ 未集成 |
| 情景记忆 (Episodic) | `data/tier3/episodic_memories.db` | SQLite | ❌ 未集成 |
| 语义记忆 (Semantic) | `data/tier4/semantic_memories.db` | SQLite | ❌ 未集成 |

**核心问题**：
- Worker 执行完任务后，经验**随会话消失**
- 下次遇到类似问题，**从零开始**
- 用户反馈**沉睡在 JSON 文件中**，不驱动任何改进
- Skillifier 学到的模式**无法跨进程持久化**

### 1.2 设计目标

将 DevSquad 从 **"无状态协作引擎"** 升级为 **"有记忆的学习型平台"**：

| 指标 | v3.0 当前（Phase 3后） | v3.1 目标 (Phase 4) | 测量方式 |
|------|---------------------|-------------------|---------|
| 跨会话知识复用 | 0%（每次冷启动） | **> 60%** 命中率 | memory recall hit rate |
| 执行经验留存 | 0%（会话结束即丢失） | **自动持久化** | memory-bank 文件增长 |
| 反馈驱动改进 | 手动查看 JSON | **自动影响下次执行** | feedback → action 链路 |
| 记忆检索延迟 | N/A（未实现） | **< 50ms** | query latency |
| 内存开销增量 | 基准 | **< 20MB** | process memory |

### 1.3 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                    MemoryBridge (记忆桥接)                     │
│                                                               │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────┐  │
│  │  MemoryWriter │   │ MemoryReader  │   │ MemoryIndexer    │  │
│  │  (写入器)    │   │ (读取器)     │   │ (索引器)         │  │
│  ├─────────────┤   ├──────────────┤   ├──────────────────┤  │
│  │ • capture_   │   │ • recall()   │   │ • rebuild_index()│  │
│  │   execution  │   │ • search_    │   │ • keyword_search │  │
│  │   _insights  │   │   knowledge  │   │ • similarity_    │  │
│  │ • record_    │   │ • get_       │   │   search         │  │
│  │   feedback   │   │   relevant_  │   │                  │  │
│  │ • persist_   │   │   history    │   │                  │  │
│  │   patterns   │   │ • query_     │   │                  │  │
│  └──────┬───────┘   │   feedback   │   └────────┬─────────┘  │
│         │           └──────┬───────┘            │            │
│         │                  │                    │            │
│  ┌──────▼──────────────────▼────────────────────▼──────────┐ │
│  │                MemoryStore (存储抽象层)                   │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │ │
│  │  │ Knowledge│ │ Episodic │ │ Semantic │ │ Feedback │  │ │
│  │  │ (JSON)   │ │ (SQLite) │ │ (SQLite) │ │ (JSON)   │  │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │ │
│  └─────────────────────────────────────────────────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  ┌──────────┐      ┌───────────┐      ┌──────────────┐
  │Coordinator│      │ Skillifier│      │PermissionGuard│
  │ 任务前召回│      │ 模式持久化 │      │ 规则学习     │
  └──────────┘      └───────────┘      └──────────────┘
```

---

## 2. 核心组件设计

### 2.1 MemoryBridge（主入口）

```python
@dataclass
class MemoryQuery:
    query_text: str
    domain: Optional[str] = None
    memory_type: Optional[MemoryType] = None
    limit: int = 5
    min_relevance: float = 0.3
    time_range: Optional[Tuple[datetime, datetime]] = None

@dataclass
class MemoryRecallResult:
    memories: List[MemoryItem]
    total_found: int
    query_time_ms: float
    hit_memory_types: Dict[str, int]

class MemoryBridge:
    """记忆桥接器 - 协作系统与持久记忆层之间的桥梁"""

    def __init__(self, base_dir: Optional[str] = None,
                 config: Optional[MemoryConfig] = None):
        self.writer: MemoryWriter = ...
        self.reader: MemoryReader = ...
        self.indexer: MemoryIndexer = ...
        self.store: MemoryStore = ...

    def recall(self, query: MemoryQuery) -> MemoryRecallResult:
        """根据查询召回相关记忆"""

    def capture_execution(self, execution: ExecutionRecord,
                          scratchpad_entries: List[ScratchpadEntry]) -> str:
        """捕获执行过程中的洞察并写入记忆"""

    def record_feedback(self, feedback: UserFeedback) -> str:
        """记录用户反馈"""

    def persist_pattern(self, pattern: SuccessPattern) -> str:
        """将 Skillifier 的成功模式持久化为知识"""

    def learn_from_mistake(self, error_context: ErrorContext) -> str:
        """从错误中学习（生成分析案例）"""

    def get_statistics(self) -> MemoryStats:
        """获取记忆库统计信息"""

    def search_knowledge(self, keywords: List[str],
                         domain: Optional[str] = None) -> List[KnowledgeItem]:
        """关键词搜索知识库"""

    def get_recent_history(self, n: int = 10) -> List[EpisodicMemory]:
        """获取最近的情景记忆"""
```

### 2.2 MemoryType（记忆类型枚举）

```python
class MemoryType(Enum):
    KNOWLEDGE = "knowledge"       # 领域知识（事实性）
    EPISODIC = "episodic"         # 情景记忆（事件性）
    SEMANTIC = "semantic"         # 语义记忆（概念性）
    FEEDBACK = "feedback"         # 用户反馈
    PATTERN = "pattern"           # 成功模式（来自 Skillifier）
    ANALYSIS = "analysis"         # 分析案例（5-Why）
    CORRECTION = "correction"     # 纠正记录（来自 tier2）
```

### 2.3 MemoryItem（统一记忆项）

```python
@dataclass
class MemoryItem:
    id: str
    memory_type: MemoryType
    title: str
    content: str
    domain: Optional[str]
    tags: List[str]
    source: str                    # 来源模块: coordinator/skillifier/user/manual
    relevance_score: float = 0.0   # 查询时的相关度 [0,1]
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def age_days(self) -> float:
        return (datetime.now() - self.created_at).days
```

### 2.4 MemoryWriter（写入器）

```python
class MemoryWriter:
    def write_knowledge(self, item: KnowledgeItem) -> str:
        """写入领域知识到 knowledge_base/domains/{domain}/"""

    def write_episodic(self, memory: EpisodicMemory) -> str:
        """写入情景记忆到 episodic_memories.db 或 JSON"""

    def write_feedback(self, feedback: UserFeedback) -> str:
        """写入用户反馈到 user_experience/feedback/"""

    def write_pattern(self, pattern: PersistedPattern) -> str:
        """写入成功模式（来自 Skillifier）"""

    def write_analysis(self, analysis: AnalysisCase) -> str:
        """写入5-Why分析案例"""

    def batch_write(self, items: List[MemoryItem]) -> int:
        """批量写入，返回成功数量"""
```

### 2.5 MemoryReader（读取器）

```python
class MemoryReader:
    def read_knowledge(self, domain: Optional[str] = None) -> List[KnowledgeItem]:
        """读取知识库条目"""

    def read_episodic(self, limit: int = 50,
                       since: Optional[datetime] = None) -> List[EpisodicMemory]:
        """读取情景记忆"""

    def read_feedback(self, status: Optional[str] = None,
                      feedback_type: Optional[str] = None) -> List[UserFeedback]:
        """读取用户反馈"""

    def read_patterns(self, category: Optional[str] = None) -> List[PersistedPattern]:
        """读取已持久化的成功模式"""

    def read_analysis_cases(self, status: Optional[str] = None) -> List[AnalysisCase]:
        """读取分析案例"""
```

### 2.6 MemoryIndexer（索引器）

```python
class MemoryIndexer:
    """内存倒排索引 + 关键词匹配"""

    def __init__(self):
        self._inverted_index: Dict[str, Set[str]] = {}  # word → {memory_id}
        self._domain_index: Dict[str, Set[str]] = {}     # domain → {memory_id}
        self._tag_index: Dict[str, Set[str]] = {}        # tag → {memory_id}
        self._type_index: Dict[MemoryType, Set[str]] = {} # type → {memory_id}
        self._tf_cache: Dict[str, Counter] = {}          # memory_id → word frequencies
        self._index_built: bool = False

    def build_index(self, items: List[MemoryItem]) -> None:
        """全量构建索引（支持增量）"""

    def add_to_index(self, item: MemoryItem) -> None:
        """增量添加单条到索引"""

    def remove_from_index(self, memory_id: str) -> None:
        """从索引移除"""

    def search(self, query_text: str,
               type_filter: Optional[MemoryType] = None,
               domain_filter: Optional[str] = None,
               limit: int = 10) -> List[Tuple[str, float]]:
        """搜索返回 [(memory_id, relevance_score), ...]"""

    def keyword_search(self, keywords: List[str],
                       domain: Optional[str] = None) -> List[Tuple[str, float]]:
        """精确关键词搜索"""

    def _compute_relevance(self, query_tokens: List[str],
                           doc_id: str) -> float:
        """TF-IDF 相关度计算"""

    def _tokenize(self, text: str) -> List[str]:
        """中文+英文分词（简化版：jieba 或基础拆分）"""
```

### 2.7 MemoryStore（存储抽象）

```python
class MemoryStore(ABC):
    @abstractmethod
    def save(self, memory_type: MemoryType, data: Dict) -> str:
        """保存数据，返回 ID"""

    @abstractmethod
    def load(self, memory_type: MemoryType,
              item_id: str) -> Optional[Dict]:
        """加载数据"""

    @abstractmethod
    def list_all(self, memory_type: MemoryType,
                 filters: Optional[Dict] = None) -> List[Dict]:
        """列出所有匹配项"""

    @abstractmethod
    def delete(self, memory_type: MemoryType, item_id: str) -> bool:
        """删除数据"""


class JsonMemoryStore(MemoryStore):
    """JSON 文件存储（用于 knowledge/feedback/analysis/pattern）"""

class SqliteMemoryStore(MemoryStore):
    """SQLite 存储（用于 episodic/semantic）"""


class CompositeMemoryStore(MemoryStore):
    """复合存储 - 按 MemoryType 路由到不同后端"""
```

### 2.8 MemoryConfig（配置）

```python
@dataclass
class MemoryConfig:
    enabled: bool = True
    base_dir: Optional[str] = None          # 默认 data/memory-bank/
    auto_capture: bool = True               # 自动捕获执行洞察
    auto_index: bool = True                 # 写入后自动更新索引
    max_episodic_memories: int = 1000       # 最大情景记忆数
    max_knowledge_items: int = 5000         # 最大知识条目数
    index_rebuild_threshold: int = 50       # 每 N 条写入后重建索引
    relevance_threshold: float = 0.3        # 最低相关度阈值
    retention_days: int = 90               # 记忆保留天数
    compress_old_memories: bool = True      # 压缩旧记忆
    enable_semantic_search: bool = False    # 语义搜索（需嵌入模型）

    @classmethod
    def default(cls) -> 'MemoryConfig':
        return cls()

    @classmethod
    def lightweight(cls) -> 'MemoryConfig':
        return cls(auto_capture=False, auto_index=False,
                    max_episodic_memories=100)

    @classmethod
    def full(cls) -> 'MemoryConfig':
        return cls(max_episodic_memories=5000,
                    max_knowledge_items=20000,
                    enable_semantic_search=True)
```

---

## 3. 协作流程集成点

### 3.1 Coordinator 集成：任务前召回

```python
# Coordinator.plan_task() 增强
def plan_task_with_memory(self, task_description, roles, bridge=None):
    if bridge:
        context = bridge.recall(MemoryQuery(
            query_text=task_description,
            limit=5
        ))
        enriched_desc = f"{task_description}\n\n历史经验:\n"
        for m in context.memories[:3]:
            enriched_desc += f"- [{m.domain}] {m.title}: {m.content[:100]}...\n"
        task_description = enriched_desc
    return self.plan_task(task_description, roles)
```

### 3.2 Skillifier 集成：模式持久化

```python
# Skillifier.generate_skill() 后自动调用
def on_skill_generated(self, proposal: SkillProposal, bridge=None):
    if bridge and proposal.quality_score >= 70:
        bridge.persist_pattern(SuccessPattern(
            name=proposal.name,
            steps_template=[s.to_dict() for s in proposal.steps],
            trigger_keywords=proposal.trigger_conditions,
            confidence=proposal.quality_score / 100.0,
        ))
```

### 3.3 Scratchpad 集成：洞察自动捕获

```python
# Worker 执行完成后，Scratchpad 中的关键发现 → 记忆
def capture_scratchpad_insights(self, scratchpad, bridge=None):
    if not bridge:
        return
    findings = scratchpad.read(query="*", entry_type=EntryType.FINDING)
    for f in findings[-5:]:
        if f.confidence > 0.7:
            bridge.capture_execution(...from finding...)
```

### 3.4 PermissionGuard 集合：规则学习

```python
# 用户 ALLOW/DECIDE 后的学习
def on_permission_decision(self, decision, bridge=None):
    if decision.outcome == DecisionOutcome.ALLOWED:
        if decision.risk_score > 0.7:
            bridge.record_feedback(UserFeedback(
                type="permission_whitelist_candidate",
                content=f"用户允许了高风险操作: {action.target}",
                context={"risk": decision.risk_score},
            ))
```

---

## 4. 记忆生命周期管理

### 4.1 记忆年龄曲线

```
新记忆 (0-7天):   完整保留，高召回权重
活跃记忆 (7-30天): 正常使用，正常权重  
成熟记忆 (30-60天): 开始压缩摘要
陈旧记忆 (60-90天): 仅保留关键结论
过期记忆 (>90天): 归档或删除
```

### 4.2 自动压缩策略

```python
def compress_old_memories(self):
    old = self.reader.read_episodic(since=cutoff_date)
    for mem in old:
        compressed = self._summarize(mem.content)
        mem.content = compressed
        metadata["compressed"] = True
        metadata["original_length"] = original_len
        self.writer.write_episodic(mem)
```

### 4.3 记忆遗忘曲线模拟

```python
def forgetting_weight(self, memory: MemoryItem) -> float:
    age = memory.age_days
    access_factor = math.log(memory.access_count + 1)
    if age < 7:
        return 1.0
    elif age < 30:
        return 0.8 * (access_factor / (access_factor + 1))
    elif age < 60:
        return 0.5 * (access_factor / (access_factor + 2))
    else:
        return 0.3 * (access_factor / (access_factor + 3))
```

---

## 5. 数据流图

### 5.1 写入流 (Capture Flow)

```
Worker完成任务
    ↓
Scratchpad 有新 FINDING?
    ├── 是 → MemoryBridge.capture_execution()
    │       ↓
    │   MemoryWriter.write_episodic()
    │       ↓
    │   MemoryIndexer.add_to_index()
    │
    ├── Skillifier 生成了高质量 Skill?
    │   → MemoryBridge.persist_pattern()
    │       ↓
    │   MemoryWriter.write_pattern()
    │
    └── 用户提供了反馈?
        → MemoryBridge.record_feedback()
            ↓
        MemoryWriter.write_feedback()
```

### 5.2 读取流 (Recall Flow)

```
Coordinator 收到新任务
    ↓
MemoryBridge.recall(query=task_description)
    ↓
MemoryIndexer.search(query_text)
    ├── 倒排索引匹配 → candidate_ids
    ├── TF-IDF 排序 → ranked_results
    └── 过滤 threshold → final_memories
    ↓
enriched_task = task + relevant_memories
    ↓
Worker 使用 enriched_task 执行
```

---

## 6. 文件结构

```
scripts/collaboration/
├── memory_bridge.py           # ★ 新增：核心模块 (~550行)
├── memory_bridge_test.py      # ★ 新增：测试 (~95 cases)
├── __init__.py                # 修改：新增导出
├── ... (已有模块不变)

data/memory-bank/
├── knowledge_base/domains/    # 已有，继续使用
├── analysis_cases/             # 已有，继续使用
├── prompt_evolution/           # 已有，只读参考
├── user_experience/feedback/   # 已有，继续使用
├── persisted_patterns/         # ★ 新增：Skillify 模式持久化
│   └── pattern_{timestamp}.json
└── index/
    └── memory_index.json       # ★ 新增：倒排索引缓存
```

---

## 7. 测试策略

### 7.1 测试分层

| 层级 | 范围 | 用例数估计 | 重点 |
|------|------|-----------|------|
| T1 | 数据模型 (10) | ~10 | MemoryItem/MemoryQuery/Config 序列化 |
| T2 | MemoryWriter (8) | ~8 | 各类型写入/JSON格式/ID生成 |
| T3 | MemoryReader (8) | ~8 | 各类型读取/过滤/分页 |
| T4 | MemoryIndexer (14) | ~14 | 索引构建/搜索/TF-IDF/增量更新 |
| T5 | MemoryBridge 核心 (14) | ~14 | recall/capture/feedback/persist/search |
| T6 | 生命周期管理 (8) | ~8 | 遗忘曲线/压缩/清理/保留策略 |
| T7 | 存储抽象层 (6) | ~6 | Composite/Json/Sqlite 路由 |
| T8 | 边界情况 (10) | ~10 | 空查询/并发/大数据量/损坏文件 |
| IT1 | Coordinator 集成 (6) | ~6 | 任务前召回/执行后捕获 |
| IT2 | Skillifier 集成 (4) | ~4 | 模式持久化/模式召回 |
| E2E | 端到端 (8) | ~8 | 完整写-索引-读-遗忘循环 |
| **合计** | | **~96** | |

### 7.2 关键验收标准

- AC-01: `recall("微服务架构设计")` 在有相关知识时返回结果 < 50ms
- AC-02: `capture_execution()` 将 Scratchpad FINDING 写入 episodic 记忆
- AC-03: `persist_pattern()` 将 Skillifier 模式写入 persisted_patterns/
- AC-04: `record_feedback()` 追加到 user_experience/feedback/
- AC-05: 索引在 500 条记忆内搜索 < 20ms
- AC-06: 90 天前的记忆被自动压缩或归档
- AC-07: 并发读写不丢失数据
- AC-08: `get_statistics()` 返回各类型记忆数量统计

---

## 8. 实施检查清单

- [ ] **C1**: 实现 MemoryType/MemoryItem/MemoryQuery/MemoryConfig 数据模型
- [ ] **C2**: 实现 MemoryStore 抽象 + JsonMemoryStore + SqliteMemoryStore + Composite
- [ ] **C3**: 实现 MemoryWriter（6 种类型的写入方法）
- [ ] **C4**: 实现 MemoryReader（6 种类型的读取方法）
- [ ] **C5**: 实现 MemoryIndexer（倒排索引 + TF-IDF 搜索 + 增量更新）
- [ ] **C6**: 实现 MemoryBridge 主类（recall/capture/record_feedback/persist/search/stats）
- [ ] **C7**: 实现生命周期管理（遗忘曲线/压缩/清理）
- [ ] **C8]: 实现 Coordinator/Skillifier 集成辅助方法
- [ ] **C9]: 编写测试用例（目标 96+ cases）
- [ ] **C10]: 集成到 __init__.py
- [ ] **C11]: 全量回归测试（472 + 96 = ~568+）
