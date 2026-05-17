# Memory Classification Engine 集成架构

> **版本**: v2.5.0
> **更新日期**: 2026-04-06

---

## 1. 架构概述

Memory Classification Engine 与 DevSquad 的深度集成架构。

```
┌─────────────────────────────────────────────────────────────────┐
│                    DevSquad                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              DualLayerContextManager                     │   │
│  │  ┌─────────────────┐    ┌─────────────────────────┐     │   │
│  │  │  GlobalContext  │    │     TaskContext         │     │   │
│  │  │  (长期记忆)      │    │     (工作记忆)           │     │   │
│  │  └────────┬────────┘    └─────────────────────────┘     │   │
│  │           │                                               │   │
│  │           ▼                                               │   │
│  │  ┌─────────────────────────────────────────────────┐     │   │
│  │  │            Memory Adapter                        │     │   │
│  │  │  ┌───────────────┐  ┌───────────────────────┐   │     │   │
│  │  │  │ TypeMapper    │  │ MemoryAdapter         │   │     │   │
│  │  │  │ (分类器)       │  │ (核心适配器)           │   │     │   │
│  │  │  └───────────────┘  └───────────────────────┘   │     │   │
│  │  └─────────────────────────────────────────────────┘     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │         Memory Classification Engine (可选)              │   │
│  │  ┌─────────────────────────────────────────────────┐     │   │
│  │  │  7 种记忆类型 + 4 层存储 + 遗忘机制              │     │   │
│  │  └─────────────────────────────────────────────────┘     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 记忆类型映射

### 2.1 七种记忆类型

| 类型 | 英文名 | 描述 | 存储层级 |
|------|--------|------|----------|
| 用户偏好 | user_preference | 用户明确表达的喜好、习惯、风格要求 | Tier 2 |
| 纠正信号 | correction | 用户纠正 AI 的判断或输出 | Tier 2 |
| 事实声明 | fact_declaration | 用户陈述的关于自身或业务的事实 | Tier 4 |
| 决策记录 | decision | 对话中达成的明确结论或选择 | Tier 3 |
| 关系信息 | relationship | 涉及人物、团队、组织之间的关系 | Tier 4 |
| 任务模式 | task_pattern | 反复出现的任务类型及其处理方式 | Tier 3 |
| 情感标记 | sentiment_marker | 用户对某话题的明确情感倾向 | Tier 2 |

### 2.2 类型识别规则

```python
# 用户偏好识别
preference_patterns = [
    '我喜欢', '我不喜欢', '我偏好', '我希望', '我习惯',
    'i prefer', 'i like', 'i want', 'my preference'
]

# 纠正信号识别
correction_patterns = [
    '不对', '错了', '不是这样', '应该是', '纠正',
    'wrong', 'incorrect', 'should be', 'correction'
]

# 事实声明识别
fact_patterns = [
    '我是', '我们公司', '我的团队', '我们的项目',
    'i am', 'my company', 'my team', 'our project'
]

# 决策记录识别
decision_patterns = [
    '决定', '选择', '确定', '就这个了', '最终方案',
    'decided', 'chosen', 'final decision', 'we will'
]
```

---

## 3. 存储层级架构

### 3.1 四层存储模型

```
┌────────────────────────────────────────────────────────────┐
│  Tier 1: 工作记忆 (Working Memory)                          │
│  - 存储: 内存 (TaskContext)                                 │
│  - 生命周期: 当前会话                                        │
│  - 用途: 当前对话上下文、临时状态                            │
├────────────────────────────────────────────────────────────┤
│  Tier 2: 程序性记忆 (Procedural Memory)                     │
│  - 存储: 配置文件 / 系统提示词                               │
│  - 生命周期: 跨会话持久化                                    │
│  - 用途: 用户偏好、工作习惯、纠正信号                        │
├────────────────────────────────────────────────────────────┤
│  Tier 3: 情节记忆 (Episodic Memory)                         │
│  - 存储: 向量数据库 (可选)                                   │
│  - 生命周期: 长期存储                                        │
│  - 用途: 决策记录、任务模式、项目历史                        │
├────────────────────────────────────────────────────────────┤
│  Tier 4: 语义记忆 (Semantic Memory)                         │
│  - 存储: 知识图谱 (可选)                                     │
│  - 生命周期: 永久存储                                        │
│  - 用途: 事实声明、关系信息、领域知识                        │
└────────────────────────────────────────────────────────────┘
```

### 3.2 层级映射关系

| 记忆类型 | 存储层级 | 注入方式 |
|----------|----------|----------|
| user_preference | Tier 2 | 系统提示词 |
| correction | Tier 2 | 系统提示词 |
| fact_declaration | Tier 4 | 知识检索 |
| decision | Tier 3 | 向量检索 |
| relationship | Tier 4 | 知识图谱 |
| task_pattern | Tier 3 | 向量检索 |
| sentiment_marker | Tier 2 | 系统提示词 |

---

## 4. 遗忘机制

### 4.1 加权衰减算法

```python
weight = base_weight * decay_factor^(age/interval) * access_frequency

# 参数说明:
# - base_weight: 初始权重 (默认 1.0)
# - decay_factor: 衰减因子 (默认 0.9)
# - age: 记忆年龄 (天)
# - interval: 衰减间隔 (天)
# - access_frequency: 访问频率
```

### 4.2 遗忘触发条件

```python
if weight < min_weight:
    # 压缩或归档记忆
    compress_memory(memory)
```

---

## 5. 模块接口

### 5.1 MemoryAdapter 核心接口

```python
class MemoryAdapter:
    def process_message(message: str, context: Dict) -> Optional[MemoryItem]:
        """处理消息并返回记忆项（如果值得记忆）"""
        
    def retrieve_memories(query: str, tier: MemoryTier, 
                         memory_type: MemoryType, limit: int) -> List[MemoryItem]:
        """检索记忆"""
        
    def apply_forgetting(decay_factor: float, min_weight: float) -> int:
        """应用遗忘机制，返回遗忘的记忆数量"""
        
    def get_statistics() -> Dict[str, Any]:
        """获取记忆统计信息"""
```

### 5.2 DualLayerContextManager 扩展接口

```python
class DualLayerContextManager:
    def process_message_with_memory(message: str, context: Dict) -> Optional[MemoryItem]:
        """使用记忆适配器处理消息"""
        
    def retrieve_memories_by_type(memory_type: str, query: str, limit: int) -> List[KnowledgeItem]:
        """按记忆类型检索"""
        
    def apply_forgetting(decay_factor: float, min_weight: float) -> Dict[str, Any]:
        """应用遗忘机制"""
        
    def get_memory_statistics() -> Dict[str, Any]:
        """获取记忆统计信息"""
```

---

## 6. 降级策略

当 Memory Classification Engine 不可用时，系统自动降级到内置简化实现：

```python
if MCE_AVAILABLE:
    self.mce_engine = MemoryClassificationEngine(config_path)
    self._use_mce = True
else:
    self.mce_engine = None
    self._use_mce = False
    # 使用本地简化实现
    self._local_memories = {tier.value: [] for tier in MemoryTier}
```

---

## 7. 文件结构

```
DevSquad/
├── scripts/
│   ├── memory_adapter.py          # 记忆适配器 (新增)
│   ├── dual_layer_context_manager.py  # 上下文管理器 (更新)
│   ├── test_memory_adapter.py     # 测试脚本 (新增)
│   └── ...
├── docs/
│   ├── architecture/
│   │   └── memory_integration_architecture.md  # 本文档
│   └── testing/
│       └── memory_integration_test.md  # 测试报告
└── ...
```

---

*文档生成时间: 2026-04-06*
